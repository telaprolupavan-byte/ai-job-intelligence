"""Shared, provider-independent HTTP access for discovery adapters (AJI-028).

A source adapter's `fetch_raw_jobs()` is the only discovery step that
touches the network. This module is the one place the rules for doing that
live, so every future adapter gets the same behavior instead of each one
re-deriving it:

- a bounded per-request timeout;
- bounded retry with exponential backoff for transient failures only
  (HTTP 429/500/502/503/504, network errors, timeouts). Any other 4xx is
  a permanent answer and is never retried;
- `Retry-After` honored exactly (delta-seconds or HTTP-date). When the
  provider asks for a longer wait than `max_retry_after_seconds`, the
  request fails instead of retrying early - never retry sooner than the
  provider asked;
- a response-size cap (declared `Content-Length` and the bytes actually
  read), so a misbehaving provider cannot exhaust memory;
- a minimum interval between requests (client-side throttle), set per
  provider from its documented rate limit;
- error messages that never include the query string, so a future
  provider's API key passed as a query parameter cannot leak into
  `DiscoveryRun.error_message` or logs.

Every failure raises `SourceHttpError`, a `JobSourceFetchError`, which the
orchestration layer already records as a failed run (HTTP 502).

Deliberately no jitter in the backoff: discovery has a single scheduler
and a run lock, so there is no herd of clients to de-synchronize, and a
deterministic schedule is simpler to test and to reason about.

Existing adapters (Greenhouse) are not migrated onto this client in
AJI-028, so their behavior stays exactly as it was.
"""

from __future__ import annotations

import email.utils
import http.client
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from services.job_discovery.sources.base import JobSourceFetchError


logger = logging.getLogger(__name__)

USER_AGENT = "NERO-JobDiscovery/1.0"

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class SourceHttpError(JobSourceFetchError):
    """A provider request failed permanently (after any retries)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class HttpPolicy:
    """Per-provider request limits. Defaults are conservative; an adapter
    passes its own values derived from the provider's documented limits."""

    timeout_seconds: float = 15.0
    max_response_bytes: int = 5 * 1024 * 1024
    # Total attempts per request, including the first one.
    max_attempts: int = 3
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 30.0
    max_retry_after_seconds: float = 120.0
    # Minimum seconds between the start of two requests (0 = no throttle).
    min_interval_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.backoff_base_seconds < 0 or self.backoff_max_seconds < 0:
            raise ValueError("backoff values cannot be negative.")
        if self.max_retry_after_seconds < 0:
            raise ValueError("max_retry_after_seconds cannot be negative.")
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds cannot be negative.")


@dataclass
class HttpResponse:
    """The transport-level result of one request."""

    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass
class HttpFetchStats:
    """Deterministic counters for one client's lifetime (one run)."""

    requests: int = 0
    retries: int = 0
    bytes_received: int = 0
    slept_seconds: float = 0.0
    status_codes: list[int] = field(default_factory=list)


# (url, headers, timeout_seconds, max_bytes) -> HttpResponse.
# Raises HttpResponseTooLarge, socket/URL errors, or TimeoutError.
Transport = Callable[[str, Mapping[str, str], float, int], HttpResponse]


class HttpResponseTooLarge(Exception):
    pass


def safe_url(url: str) -> str:
    """scheme://host/path only - never the query string or fragment."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _read_capped(stream: Any, max_bytes: int) -> bytes:
    body = stream.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise HttpResponseTooLarge()
    return body


def _check_declared_length(headers: Mapping[str, str], max_bytes: int) -> None:
    declared = headers.get("Content-Length")
    if declared is None:
        return
    try:
        if int(declared) > max_bytes:
            raise HttpResponseTooLarge()
    except ValueError:
        return


def urllib_transport(
    url: str,
    headers: Mapping[str, str],
    timeout_seconds: float,
    max_bytes: int,
) -> HttpResponse:
    """Default transport: stdlib urllib (the same client Greenhouse uses -
    no new dependency). Non-2xx statuses are returned, not raised, so the
    retry policy sees them uniformly."""
    request = urllib.request.Request(url, headers=dict(headers), method="GET")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_headers = dict(response.headers.items())
            _check_declared_length(response_headers, max_bytes)
            return HttpResponse(
                status=response.status,
                headers=response_headers,
                body=_read_capped(response, max_bytes),
            )
    except urllib.error.HTTPError as exc:
        error_headers = dict(exc.headers.items()) if exc.headers else {}
        _check_declared_length(error_headers, max_bytes)
        try:
            body = _read_capped(exc, max_bytes)
        except HttpResponseTooLarge:
            body = b""
        return HttpResponse(status=exc.code, headers=error_headers, body=body)


def parse_retry_after(value: str | None, *, now: datetime) -> float | None:
    """Seconds to wait per a `Retry-After` header, or None if absent or
    unreadable. Supports both forms in RFC 9110: delta-seconds and an
    HTTP-date (a date in the past means "now", i.e. 0)."""
    if value is None:
        return None

    text = value.strip()
    if not text:
        return None

    if text.isdigit():
        return float(int(text))

    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None

    if when is None:
        return None

    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    return max(0.0, (when - now).total_seconds())


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


class SourceHttpClient:
    """Rate-aware JSON GET client for one provider. Create one per run so
    the throttle and stats cover exactly that run."""

    def __init__(
        self,
        *,
        source_name: str,
        policy: HttpPolicy | None = None,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not source_name:
            raise ValueError("source_name is required.")

        self.source_name = source_name
        self.policy = policy or HttpPolicy()
        self._transport = transport or urllib_transport
        self._sleep = sleep
        self._clock = clock
        self._now = now
        self._last_request_started: float | None = None
        self.stats = HttpFetchStats()

    def _wait(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self.stats.slept_seconds += seconds
        self._sleep(seconds)

    def _throttle(self) -> None:
        interval = self.policy.min_interval_seconds
        if interval <= 0 or self._last_request_started is None:
            return
        elapsed = self._clock() - self._last_request_started
        self._wait(interval - elapsed)

    def _backoff_seconds(self, attempt: int) -> float:
        delay = self.policy.backoff_base_seconds * (2 ** (attempt - 1))
        return min(delay, self.policy.backoff_max_seconds)

    def _retry_delay(
        self, attempt: int, response: HttpResponse | None, shown_url: str
    ) -> float:
        """Seconds before the next attempt, or raise when the provider asked
        for a longer wait than this policy allows."""
        backoff = self._backoff_seconds(attempt)

        if response is None:
            return backoff

        retry_after = parse_retry_after(
            _header(response.headers, "Retry-After"), now=self._now()
        )
        if retry_after is None:
            return backoff

        if retry_after > self.policy.max_retry_after_seconds:
            raise SourceHttpError(
                f"{self.source_name} asked to retry after {retry_after:.0f}s "
                f"(limit {self.policy.max_retry_after_seconds:.0f}s) for "
                f"{shown_url}; not retrying early.",
                status_code=response.status,
                retryable=True,
            )

        return max(retry_after, backoff)

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """GET `url` and decode JSON, applying the full policy. Raises
        SourceHttpError on any permanent failure."""
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise SourceHttpError(
                f"{self.source_name}: refusing non-http(s) URL."
            )

        request_headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        }
        policy = self.policy
        shown_url = safe_url(url)

        for attempt in range(1, policy.max_attempts + 1):
            self._throttle()
            self._last_request_started = self._clock()
            self.stats.requests += 1
            started = self._clock()

            response: HttpResponse | None = None
            failure: str

            try:
                response = self._transport(
                    url,
                    request_headers,
                    policy.timeout_seconds,
                    policy.max_response_bytes,
                )
            except HttpResponseTooLarge:
                raise SourceHttpError(
                    f"{self.source_name} response from {shown_url} exceeded "
                    f"{policy.max_response_bytes} bytes."
                ) from None
            except (OSError, http.client.HTTPException) as exc:
                # URLError, timeouts, and connection resets are all OSError.
                failure = f"network error: {type(exc).__name__}: {exc}"
            else:
                self.stats.status_codes.append(response.status)
                self.stats.bytes_received += len(response.body)

                if 200 <= response.status < 300:
                    logger.info(
                        "discovery http: source=%s url=%s status=%d "
                        "attempt=%d bytes=%d latency_ms=%.0f",
                        self.source_name,
                        shown_url,
                        response.status,
                        attempt,
                        len(response.body),
                        (self._clock() - started) * 1000,
                    )
                    try:
                        return json.loads(response.body.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise SourceHttpError(
                            f"{self.source_name} returned invalid JSON from "
                            f"{shown_url}."
                        ) from exc

                if response.status not in RETRYABLE_STATUS_CODES:
                    raise SourceHttpError(
                        f"{self.source_name} returned HTTP {response.status} "
                        f"for {shown_url}.",
                        status_code=response.status,
                    )

                failure = f"HTTP {response.status}"

            if attempt == policy.max_attempts:
                raise SourceHttpError(
                    f"{self.source_name} request to {shown_url} failed after "
                    f"{attempt} attempt(s): {failure}",
                    status_code=response.status if response else None,
                    retryable=True,
                )

            delay = self._retry_delay(attempt, response, shown_url)
            logger.warning(
                "discovery http retry: source=%s url=%s attempt=%d/%d "
                "reason=%s wait_s=%.1f",
                self.source_name,
                shown_url,
                attempt,
                policy.max_attempts,
                failure,
                delay,
            )
            self.stats.retries += 1
            self._wait(delay)

        raise AssertionError("unreachable")  # pragma: no cover
