import json
import urllib.error
import urllib.request
from datetime import datetime

import pytest

from services.job_discovery.sources.theirstack import (
    SEARCH_URL,
    TheirStackAdapterError,
    TheirStackAuthenticationError,
    TheirStackJobSource,
    TheirStackRateLimitError,
    TheirStackTransientError,
)


SAMPLE_JOB_FULL = {
    "id": "job-1001",
    "job_title": "Senior Machine Learning Engineer",
    "company": {"name": "Example Inc"},
    "description": "Build ML systems.",
    "long_location": "New York, NY, United States",
    "country": "US",
    "remote": True,
    "employment_statuses": ["Full-time"],
    "url": "https://boards.theirstack.com/example/jobs/1001",
    "final_url": "https://careers.example.com/jobs/1001",
    "date_posted": "2026-01-10T12:00:00Z",
    "min_annual_salary": 150000,
    "max_annual_salary": 200000,
    "salary_currency": "USD",
}

SAMPLE_JOB_MINIMAL = {
    "id": "job-1002",
    "job_title": "Platform Engineer",
    "company": {"name": "Minimal Co"},
}


class _FakeResponse:
    def __init__(self, payload: dict, *, status: int = 200):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_urlopen_returning(payload: dict):
    def _fake(request, timeout=None):
        assert request.full_url == SEARCH_URL
        assert request.get_header("Authorization") == "Bearer test-api-key"
        return _FakeResponse(payload)

    return _fake


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Retry backoff should never slow down the unit test suite."""
    monkeypatch.setattr(
        "services.job_discovery.sources.theirstack.time.sleep",
        lambda seconds: None,
    )


def test_fetch_jobs_parses_full_and_minimal_jobs(monkeypatch):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _fake_urlopen_returning({"data": [SAMPLE_JOB_FULL, SAMPLE_JOB_MINIMAL]}),
    )

    source = TheirStackJobSource(api_key="test-api-key", max_results=10)
    jobs = source.fetch_jobs()

    assert len(jobs) == 2

    full = jobs[0]
    assert full.source == "theirstack"
    assert full.source_job_id == "job-1001"
    assert full.title == "Senior Machine Learning Engineer"
    assert full.company == "Example Inc"
    assert full.description == "Build ML systems."
    assert full.country == "USA"
    assert full.remote_type == "remote"
    assert full.employment_type == "full_time"
    assert full.source_url == "https://careers.example.com/jobs/1001"
    assert full.application_url == "https://boards.theirstack.com/example/jobs/1001"
    assert full.posted_at == datetime.fromisoformat("2026-01-10T12:00:00+00:00")
    assert full.salary_min == 150000
    assert full.salary_max == 200000
    assert full.salary_currency == "USD"

    # Missing optional fields (no location/country/remote/employment/url/
    # salary/date) must come through as None, never a fabricated value.
    minimal = jobs[1]
    assert minimal.source_job_id == "job-1002"
    assert minimal.title == "Platform Engineer"
    assert minimal.company == "Minimal Co"
    assert minimal.description is None
    assert minimal.location is None
    assert minimal.country == ""
    assert minimal.remote_type is None
    assert minimal.employment_type is None
    assert minimal.salary_min is None
    assert minimal.salary_max is None
    assert minimal.posted_at is None
    assert minimal.application_url is None
    assert minimal.source_url is None


def test_non_us_country_is_not_marked_as_us(monkeypatch):
    job = dict(SAMPLE_JOB_MINIMAL, country="DE")
    monkeypatch.setattr(
        urllib.request, "urlopen", _fake_urlopen_returning({"data": [job]})
    )

    source = TheirStackJobSource(api_key="test-api-key")
    jobs = source.fetch_jobs()

    assert jobs[0].country == ""


def test_remote_false_is_not_mapped_to_onsite(monkeypatch):
    """A bare `remote: false` only tells us "not confirmed remote" - it
    must not be reported as "onsite", which the provider never said."""
    job = dict(SAMPLE_JOB_MINIMAL, remote=False)
    monkeypatch.setattr(
        urllib.request, "urlopen", _fake_urlopen_returning({"data": [job]})
    )

    source = TheirStackJobSource(api_key="test-api-key")
    jobs = source.fetch_jobs()

    assert jobs[0].remote_type is None


def test_malformed_response_missing_data_list_raises_adapter_error(monkeypatch):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        _fake_urlopen_returning({"unexpected": "shape"}),
    )

    source = TheirStackJobSource(api_key="test-api-key")

    with pytest.raises(TheirStackAdapterError):
        source.fetch_jobs()


def test_invalid_json_response_raises_adapter_error(monkeypatch):
    class _BadResponse:
        def read(self):
            return b"not json"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda request, timeout=None: _BadResponse()
    )

    source = TheirStackJobSource(api_key="test-api-key")

    with pytest.raises(TheirStackAdapterError):
        source.fetch_jobs()


def test_network_failure_raises_transient_error_after_retries(monkeypatch):
    calls = {"count": 0}

    def _fake_urlopen(request, timeout=None):
        calls["count"] += 1
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key="test-api-key", max_retries=2)

    with pytest.raises(TheirStackTransientError):
        source.fetch_jobs()

    # Initial attempt + max_retries retries, bounded - not unlimited.
    assert calls["count"] == 3


def test_server_error_is_retried_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def _fake_urlopen(request, timeout=None):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.HTTPError(
                request.full_url, 503, "Service Unavailable", {}, None
            )
        return _FakeResponse({"data": [SAMPLE_JOB_MINIMAL]})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key="test-api-key", max_retries=2)
    jobs = source.fetch_jobs()

    assert len(jobs) == 1
    assert calls["count"] == 3


def test_authentication_failure_is_never_retried(monkeypatch):
    calls = {"count": 0}

    def _fake_urlopen(request, timeout=None):
        calls["count"] += 1
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key="wrong-key", max_retries=3)

    with pytest.raises(TheirStackAuthenticationError):
        source.fetch_jobs()

    assert calls["count"] == 1


def test_forbidden_is_also_treated_as_authentication_failure(monkeypatch):
    def _fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key="test-api-key")

    with pytest.raises(TheirStackAuthenticationError):
        source.fetch_jobs()


def test_rate_limit_is_retried_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def _fake_urlopen(request, timeout=None):
        calls["count"] += 1
        if calls["count"] < 2:
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests", {}, None
            )
        return _FakeResponse({"data": [SAMPLE_JOB_MINIMAL]})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key="test-api-key", max_retries=2)
    jobs = source.fetch_jobs()

    assert len(jobs) == 1
    assert calls["count"] == 2


def test_rate_limit_exhausting_retries_raises(monkeypatch):
    def _fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 429, "Too Many Requests", {}, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key="test-api-key", max_retries=1)

    with pytest.raises(TheirStackRateLimitError):
        source.fetch_jobs()


def test_pagination_fetches_multiple_pages_up_to_max_results(monkeypatch):
    requests_seen = []

    def _fake_urlopen(request, timeout=None):
        body = json.loads(request.data.decode("utf-8"))
        requests_seen.append(body)

        page = body["page"]
        limit = body["limit"]

        if page == 0:
            jobs = [dict(SAMPLE_JOB_MINIMAL, id=f"page0-{i}") for i in range(limit)]
        elif page == 1:
            jobs = [dict(SAMPLE_JOB_MINIMAL, id=f"page1-{i}") for i in range(2)]
        else:
            jobs = []

        return _FakeResponse({"data": jobs})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(
        api_key="test-api-key", max_results=7, page_size=5
    )
    jobs = source.fetch_jobs()

    # Page 0 returns a full page (5, == limit) so pagination continues;
    # page 1 fills the remaining quota exactly (2 of 2 remaining), so
    # max_results is reached and no further, unnecessary request is made.
    assert len(jobs) == 7
    assert len(requests_seen) == 2
    assert requests_seen[0] == {
        "page": 0,
        "limit": 5,
        "posted_at_max_age_days": 7,
        "job_country_code_or": ["US"],
    }
    assert requests_seen[1]["page"] == 1
    assert requests_seen[1]["limit"] == 2


def test_pagination_never_exceeds_configured_max_results(monkeypatch):
    def _fake_urlopen(request, timeout=None):
        body = json.loads(request.data.decode("utf-8"))
        limit = body["limit"]
        jobs = [dict(SAMPLE_JOB_MINIMAL, id=f"j-{body['page']}-{i}") for i in range(limit)]
        return _FakeResponse({"data": jobs})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(
        api_key="test-api-key", max_results=12, page_size=5
    )
    jobs = source.fetch_jobs()

    assert len(jobs) == 12


def test_missing_api_key_raises_value_error():
    with pytest.raises(ValueError):
        TheirStackJobSource(api_key="")


def test_non_positive_max_results_raises_value_error():
    with pytest.raises(ValueError):
        TheirStackJobSource(api_key="test-api-key", max_results=0)


def test_job_title_and_country_filters_are_sent_when_provided(monkeypatch):
    captured = {}

    def _fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"data": []})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(
        api_key="test-api-key",
        job_title_or=["Software Engineer", "Data Scientist"],
        job_country_code_or=["US"],
        posted_at_max_age_days=3,
    )
    source.fetch_jobs()

    assert captured["body"]["job_title_or"] == ["Software Engineer", "Data Scientist"]
    assert captured["body"]["job_country_code_or"] == ["US"]
    assert captured["body"]["posted_at_max_age_days"] == 3


def test_no_api_key_leakage_in_errors_or_repr(monkeypatch):
    """THEIRSTACK_API_KEY must never appear in an exception message (which
    can end up in a DiscoveryRun.error_message row, logs, or an HTTP error
    response) - see apps/api/services/job_discovery_service.py."""
    secret_key = "sk-super-secret-theirstack-key-do-not-leak"

    def _fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key=secret_key)

    with pytest.raises(TheirStackAuthenticationError) as exc_info:
        source.fetch_jobs()

    assert secret_key not in str(exc_info.value)
    assert secret_key not in repr(exc_info.value)


def test_api_key_is_sent_only_in_the_authorization_header_never_in_the_url(
    monkeypatch,
):
    """The key must travel as a Bearer credential on the Authorization
    header only - never as a query parameter or part of the request URL,
    where it would be far more likely to end up captured in an access
    log somewhere outside this application's control."""
    secret_key = "sk-super-secret-theirstack-key-do-not-leak"
    captured_requests = []

    def _fake_urlopen(request, timeout=None):
        captured_requests.append(request)
        return _FakeResponse({"data": []})

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key=secret_key)
    source.fetch_jobs()

    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert secret_key not in request.full_url
    assert secret_key not in (request.data or b"").decode("utf-8")
    assert request.get_header("Authorization") == f"Bearer {secret_key}"


def test_transient_network_error_message_never_contains_api_key(monkeypatch):
    secret_key = "sk-super-secret-theirstack-key-do-not-leak"

    def _fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    source = TheirStackJobSource(api_key=secret_key, max_retries=0)

    with pytest.raises(TheirStackTransientError) as exc_info:
        source.fetch_jobs()

    assert secret_key not in str(exc_info.value)
