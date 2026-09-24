"""AJI-028 - the shared discovery HTTP client: timeout, retry/backoff,
Retry-After, response-size cap, throttle, and safe error messages.

Everything runs offline: a scripted fake transport plus a fake clock whose
`sleep` advances time, so every wait is asserted exactly. One section uses
a real loopback HTTP server to cover the default urllib transport.
"""

from __future__ import annotations

import json
import threading
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from services.job_discovery.source_http import (
    USER_AGENT,
    HttpPolicy,
    HttpResponse,
    HttpResponseTooLarge,
    SourceHttpClient,
    SourceHttpError,
    parse_retry_after,
    safe_url,
    urllib_transport,
)
from services.job_discovery.sources.base import JobSourceFetchError


URL = "https://jobs.provider.example/api/jobs?page=1&api_key=SECRET123"
NOW = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class ScriptedTransport:
    """Returns (or raises) each scripted outcome in order."""

    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def __call__(self, url, headers, timeout_seconds, max_bytes):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "timeout": timeout_seconds,
                "max_bytes": max_bytes,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def ok(payload=None, **headers) -> HttpResponse:
    return HttpResponse(
        status=200,
        headers=headers,
        body=json.dumps(payload if payload is not None else {"jobs": []}).encode(),
    )


def status(code: int, **headers) -> HttpResponse:
    return HttpResponse(status=code, headers=headers, body=b"")


def make_client(transport, clock=None, **policy) -> tuple[SourceHttpClient, FakeClock]:
    clock = clock or FakeClock()
    client = SourceHttpClient(
        source_name="provider_example",
        policy=HttpPolicy(**policy),
        transport=transport,
        sleep=clock.sleep,
        clock=clock.clock,
        now=lambda: NOW,
    )
    return client, clock


# ---------------------------------------------------------------------------
# Success path, timeout, headers
# ---------------------------------------------------------------------------


def test_success_decodes_json_and_passes_bounded_timeout_and_headers():
    transport = ScriptedTransport(ok({"jobs": [1, 2]}))
    client, clock = make_client(transport, timeout_seconds=7.5, max_response_bytes=4096)

    assert client.get_json(URL, headers={"X-Extra": "1"}) == {"jobs": [1, 2]}

    call = transport.calls[0]
    assert call["timeout"] == 7.5
    assert call["max_bytes"] == 4096
    assert call["headers"]["User-Agent"] == USER_AGENT
    assert call["headers"]["Accept"] == "application/json"
    assert call["headers"]["X-Extra"] == "1"
    assert clock.sleeps == []
    assert client.stats.requests == 1
    assert client.stats.retries == 0


def test_errors_are_job_source_fetch_errors_so_runs_record_them():
    assert issubclass(SourceHttpError, JobSourceFetchError)


@pytest.mark.parametrize("bad_url", ["ftp://x.example/a", "file:///etc/passwd", "/relative"])
def test_non_http_urls_are_refused_without_a_request(bad_url):
    transport = ScriptedTransport()
    client, _ = make_client(transport)

    with pytest.raises(SourceHttpError):
        client.get_json(bad_url)

    assert transport.calls == []


# ---------------------------------------------------------------------------
# Retry / backoff
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_status_is_retried_with_exponential_backoff(code):
    transport = ScriptedTransport(status(code), status(code), ok())
    client, clock = make_client(transport, max_attempts=3, backoff_base_seconds=2.0)

    assert client.get_json(URL) == {"jobs": []}

    assert len(transport.calls) == 3
    assert clock.sleeps == [2.0, 4.0]
    assert client.stats.retries == 2
    assert client.stats.status_codes == [code, code, 200]


def test_backoff_is_capped():
    transport = ScriptedTransport(status(503), status(503), status(503), ok())
    client, clock = make_client(
        transport, max_attempts=4, backoff_base_seconds=10.0, backoff_max_seconds=15.0
    )

    client.get_json(URL)

    assert clock.sleeps == [10.0, 15.0, 15.0]


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("dns failure"),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
    ],
)
def test_network_errors_and_timeouts_are_retried(error):
    transport = ScriptedTransport(error, ok())
    client, clock = make_client(transport, backoff_base_seconds=1.0)

    assert client.get_json(URL) == {"jobs": []}
    assert clock.sleeps == [1.0]


def test_retries_are_bounded_and_the_final_error_is_raised():
    transport = ScriptedTransport(status(503), status(503), status(503))
    client, clock = make_client(transport, max_attempts=3, backoff_base_seconds=1.0)

    with pytest.raises(SourceHttpError) as exc_info:
        client.get_json(URL)

    assert len(transport.calls) == 3
    assert clock.sleeps == [1.0, 2.0]
    assert exc_info.value.status_code == 503
    assert exc_info.value.retryable is True
    assert "after 3 attempt(s)" in str(exc_info.value)


@pytest.mark.parametrize("code", [400, 401, 403, 404, 410, 422])
def test_permanent_client_errors_are_never_retried(code):
    transport = ScriptedTransport(status(code))
    client, clock = make_client(transport, max_attempts=5)

    with pytest.raises(SourceHttpError) as exc_info:
        client.get_json(URL)

    assert len(transport.calls) == 1
    assert clock.sleeps == []
    assert exc_info.value.status_code == code
    assert exc_info.value.retryable is False


def test_single_attempt_policy_never_retries():
    transport = ScriptedTransport(status(503))
    client, clock = make_client(transport, max_attempts=1)

    with pytest.raises(SourceHttpError):
        client.get_json(URL)

    assert len(transport.calls) == 1
    assert clock.sleeps == []


def test_invalid_json_fails_without_retry():
    transport = ScriptedTransport(HttpResponse(status=200, headers={}, body=b"<html>"))
    client, _ = make_client(transport)

    with pytest.raises(SourceHttpError, match="invalid JSON"):
        client.get_json(URL)

    assert len(transport.calls) == 1


# ---------------------------------------------------------------------------
# Retry-After
# ---------------------------------------------------------------------------


def test_retry_after_seconds_is_honored_over_shorter_backoff():
    transport = ScriptedTransport(status(429, **{"Retry-After": "12"}), ok())
    client, clock = make_client(transport, backoff_base_seconds=1.0)

    client.get_json(URL)

    assert clock.sleeps == [12.0]


def test_backoff_wins_when_retry_after_is_shorter():
    transport = ScriptedTransport(status(503, **{"retry-after": "1"}), ok())
    client, clock = make_client(transport, backoff_base_seconds=5.0)

    client.get_json(URL)

    assert clock.sleeps == [5.0]


def test_retry_after_http_date_is_honored():
    header = "Thu, 24 Sep 2026 12:00:30 GMT"  # NOW + 30s
    transport = ScriptedTransport(status(429, **{"Retry-After": header}), ok())
    client, clock = make_client(transport, backoff_base_seconds=1.0)

    client.get_json(URL)

    assert clock.sleeps == [30.0]


def test_retry_after_longer_than_the_limit_fails_instead_of_retrying_early():
    transport = ScriptedTransport(status(429, **{"Retry-After": "3600"}), ok())
    client, clock = make_client(transport, max_retry_after_seconds=120.0)

    with pytest.raises(SourceHttpError, match="not retrying early") as exc_info:
        client.get_json(URL)

    assert len(transport.calls) == 1
    assert clock.sleeps == []
    assert exc_info.value.status_code == 429


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("0", 0.0),
        ("45", 45.0),
        ("not a date", None),
        ("Thu, 24 Sep 2026 12:01:00 GMT", 60.0),
        ("Thu, 24 Sep 2026 11:00:00 GMT", 0.0),  # in the past -> now
    ],
)
def test_parse_retry_after(value, expected):
    assert parse_retry_after(value, now=NOW) == expected


# ---------------------------------------------------------------------------
# Response-size limit
# ---------------------------------------------------------------------------


def test_response_too_large_fails_without_retry():
    transport = ScriptedTransport(HttpResponseTooLarge(), ok())
    client, clock = make_client(transport, max_response_bytes=10)

    with pytest.raises(SourceHttpError, match="exceeded 10 bytes"):
        client.get_json(URL)

    assert len(transport.calls) == 1
    assert clock.sleeps == []


# ---------------------------------------------------------------------------
# Throttling
# ---------------------------------------------------------------------------


def test_throttle_spaces_consecutive_requests():
    transport = ScriptedTransport(ok(), ok(), ok())
    client, clock = make_client(transport, min_interval_seconds=1.5)

    client.get_json(URL)
    client.get_json(URL)
    clock.now += 0.5  # the caller spent 0.5s between requests
    client.get_json(URL)

    # First request is immediate; each later one waits out the rest of
    # the interval since the previous request started.
    assert clock.sleeps == [1.5, 1.0]


def test_no_throttle_wait_once_the_interval_already_elapsed():
    transport = ScriptedTransport(ok(), ok())
    client, clock = make_client(transport, min_interval_seconds=1.0)

    client.get_json(URL)
    clock.now += 5.0
    client.get_json(URL)

    assert clock.sleeps == []


def test_throttle_also_applies_between_retries():
    transport = ScriptedTransport(status(503), ok())
    client, clock = make_client(
        transport, min_interval_seconds=3.0, backoff_base_seconds=1.0
    )

    client.get_json(URL)

    # 1s backoff, then the remaining 2s of the 3s interval.
    assert clock.sleeps == [1.0, 2.0]
    assert client.stats.slept_seconds == 3.0


# ---------------------------------------------------------------------------
# Safe error messages (no query strings / credentials)
# ---------------------------------------------------------------------------


def test_safe_url_drops_query_and_fragment():
    assert safe_url(URL + "#frag") == "https://jobs.provider.example/api/jobs"


@pytest.mark.parametrize(
    "outcomes",
    [
        (status(404),),
        (status(503), status(503), status(503)),
        (HttpResponse(status=200, headers={}, body=b"nope"),),
        (HttpResponseTooLarge(),),
        (status(429, **{"Retry-After": "9999"}),),
    ],
)
def test_error_messages_never_include_the_query_string(outcomes):
    client, _ = make_client(ScriptedTransport(*outcomes))

    with pytest.raises(SourceHttpError) as exc_info:
        client.get_json(URL)

    assert "SECRET123" not in str(exc_info.value)
    assert "api_key" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Policy validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"timeout_seconds": 0},
        {"max_response_bytes": 0},
        {"max_attempts": 0},
        {"backoff_base_seconds": -1},
        {"max_retry_after_seconds": -1},
        {"min_interval_seconds": -1},
    ],
)
def test_invalid_policies_are_rejected(overrides):
    with pytest.raises(ValueError):
        HttpPolicy(**overrides)


def test_source_name_is_required():
    with pytest.raises(ValueError):
        SourceHttpClient(source_name="")


# ---------------------------------------------------------------------------
# Default urllib transport against a real loopback server
# ---------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):  # noqa: N802 - http.server API
        code, headers, body = self.routes[self.path.split("?")[0]]
        self.send_response(code)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def loopback():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", _Handler.routes
    finally:
        server.shutdown()
        server.server_close()
        _Handler.routes.clear()


def test_urllib_transport_reads_success(loopback):
    base, routes = loopback
    routes["/ok"] = (200, {"Content-Type": "application/json"}, b'{"a": 1}')

    response = urllib_transport(base + "/ok", {}, 5.0, 1024)

    assert response.status == 200
    assert response.body == b'{"a": 1}'


def test_urllib_transport_returns_error_statuses_with_headers(loopback):
    base, routes = loopback
    routes["/limited"] = (429, {"Retry-After": "3"}, b"slow down")

    response = urllib_transport(base + "/limited", {}, 5.0, 1024)

    assert response.status == 429
    assert response.headers["Retry-After"] == "3"


def test_urllib_transport_enforces_the_size_cap_on_actual_bytes(loopback):
    base, routes = loopback
    # No Content-Length: the cap must still hold on what is read.
    routes["/big"] = (200, {}, b"x" * 2048)

    with pytest.raises(HttpResponseTooLarge):
        urllib_transport(base + "/big", {}, 5.0, 1024)


def test_urllib_transport_rejects_a_declared_oversized_body(loopback):
    base, routes = loopback
    routes["/declared"] = (200, {"Content-Length": "999999"}, b"{}")

    with pytest.raises(HttpResponseTooLarge):
        urllib_transport(base + "/declared", {}, 5.0, 1024)


def test_client_with_default_transport_end_to_end(loopback):
    base, routes = loopback
    routes["/jobs"] = (200, {"Content-Type": "application/json"}, b'{"jobs": []}')

    client = SourceHttpClient(source_name="loopback")

    assert client.get_json(base + "/jobs?page=1") == {"jobs": []}
    assert client.stats.requests == 1
