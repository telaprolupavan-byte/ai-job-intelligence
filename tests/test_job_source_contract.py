"""AJI-028 - one contract every discovery adapter must satisfy, run
against every adapter in the codebase (Greenhouse, the synthetic test
fixture, and the synthetic paged test double built on the AJI-028
foundation), plus the registry rules that bind adapters to attribution.

Greenhouse and the test fixture are exercised exactly as they are: these
tests pin that AJI-028 left their behavior unchanged.
"""

from __future__ import annotations

import copy
import json
import urllib.request
from datetime import datetime

import pytest

from apps.api.services import job_discovery_service
from services.job_discovery.attribution import get_source_attribution
from services.job_discovery.contracts import (
    RESERVED_USER_SUBMITTED_SOURCE,
    DiscoveredJob,
    RawProviderJob,
)
from services.job_discovery.pipeline import normalize_raw_jobs
from services.job_discovery.sources.greenhouse import GreenhouseJobSource
from services.job_discovery.sources.test_fixture import (
    TEST_FIXTURE_SOURCE,
    TestFixtureJobSource,
)
from tests.job_discovery_fakes import (
    ExamplePagedSource,
    PagedTransport,
    example_record,
)


GREENHOUSE_PAYLOAD = {
    "jobs": [
        {
            "id": 1001,
            "title": "Senior Machine Learning Engineer",
            "location": {"name": "New York, NY"},
            "content": "<p>Build <b>ML</b> systems for real users.</p>",
            "absolute_url": "https://boards.greenhouse.io/example/jobs/1001",
            "updated_at": "2026-01-10T12:00:00-05:00",
            "metadata": [{"name": "Employment Type", "value": "Full-time"}],
        },
        {"title": "No id"},
    ]
}


class _FakeUrlopenResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _greenhouse(monkeypatch):
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: _FakeUrlopenResponse(GREENHOUSE_PAYLOAD),
    )
    return GreenhouseJobSource(board_token="example", company_name="Example Inc")


def _fixture(monkeypatch):
    return TestFixtureJobSource()


def _paged(monkeypatch):
    records = [
        example_record("a", expires=1_900_000_000),
        example_record("b"),
        example_record("c", countries=[]),
        {"title": "no guid"},
    ]
    return ExamplePagedSource(PagedTransport(records, page_size=2))


ADAPTER_FACTORIES = {
    "greenhouse": _greenhouse,
    "test_fixture": _fixture,
    "example_paged": _paged,
}


@pytest.fixture(params=sorted(ADAPTER_FACTORIES))
def adapter(request, monkeypatch):
    return ADAPTER_FACTORIES[request.param](monkeypatch)


def test_adapter_identity(adapter):
    assert isinstance(adapter.source_name, str) and adapter.source_name.strip()
    assert adapter.source_name != RESERVED_USER_SUBMITTED_SOURCE
    assert isinstance(adapter.is_test_provider, bool)


def test_fetch_returns_raw_records_stamped_with_the_source(adapter):
    raw_jobs = adapter.fetch_raw_jobs()

    assert raw_jobs
    for raw_job in raw_jobs:
        assert isinstance(raw_job, RawProviderJob)
        assert raw_job.source == adapter.source_name
        assert isinstance(raw_job.payload, dict)


def test_normalization_is_deterministic_and_does_not_mutate_input(adapter):
    for raw_job in adapter.fetch_raw_jobs():
        before = copy.deepcopy(raw_job.payload)
        try:
            first = adapter.normalize_raw_job(raw_job)
        except Exception:  # noqa: BLE001 - a malformed record may raise
            assert raw_job.payload == before
            continue
        second = adapter.normalize_raw_job(raw_job)

        assert first == second
        assert raw_job.payload == before


def test_normalized_jobs_honor_the_canonical_contract(adapter):
    normalized, errors = normalize_raw_jobs(adapter, adapter.fetch_raw_jobs())

    assert normalized
    for job in normalized:
        assert isinstance(job, DiscoveredJob)
        assert job.source == adapter.source_name
        for url in (job.source_url, job.application_url):
            assert url is None or url.startswith(("http://", "https://"))
        for moment in (job.posted_at, job.expires_at):
            assert moment is None or isinstance(moment, datetime)
    # Malformed records are isolated as rejections, never a failed batch.
    for error in errors:
        assert error.reason.startswith("Normalization failed")


# ---------------------------------------------------------------------------
# Existing adapters unchanged by AJI-028
# ---------------------------------------------------------------------------


def test_greenhouse_never_states_an_expiry(monkeypatch):
    source = _greenhouse(monkeypatch)
    normalized, errors = normalize_raw_jobs(source, source.fetch_raw_jobs())

    assert [job.source_job_id for job in normalized] == ["1001"]
    assert all(job.expires_at is None for job in normalized)
    assert len(errors) == 1  # the record without an id


def test_test_fixture_output_is_unchanged():
    source = TestFixtureJobSource()
    normalized, errors = normalize_raw_jobs(source, source.fetch_raw_jobs())

    assert source.source_name == TEST_FIXTURE_SOURCE
    assert source.is_test_provider is True
    assert len(source.fetch_raw_jobs()) == 9
    assert len(normalized) == 8
    assert len(errors) == 1
    assert all(job.expires_at is None for job in normalized)


# ---------------------------------------------------------------------------
# The synthetic paged adapter: foundation rules in practice
# ---------------------------------------------------------------------------


def test_paged_adapter_reads_at_most_the_approved_pages():
    records = [example_record(str(i)) for i in range(40)]
    transport = PagedTransport(records, page_size=2)
    source = ExamplePagedSource(transport)

    raw_jobs = source.fetch_raw_jobs()

    assert len(transport.urls) == 5
    assert len(raw_jobs) == 10
    assert source.last_fetch.truncated is True


def test_paged_adapter_maps_only_explicit_us_eligibility_and_stated_expiry():
    records = [
        example_record("us", expires=1_900_000_000),
        example_record("world", countries=[]),
        example_record("ca", countries=["Canada"]),
    ]
    source = ExamplePagedSource(PagedTransport(records, page_size=5))

    jobs = {
        job.source_job_id.rsplit("/", 1)[1]: job
        for job in (source.normalize_raw_job(r) for r in source.fetch_raw_jobs())
    }

    assert jobs["us"].country == "USA"
    assert jobs["us"].expires_at is not None
    assert jobs["world"].country == ""  # worldwide is not U.S.-eligible
    assert jobs["world"].expires_at is None  # no stated expiry: none invented
    assert jobs["ca"].country == ""


# ---------------------------------------------------------------------------
# Provider selection and attribution registry rules
# ---------------------------------------------------------------------------


def test_every_real_supported_provider_has_a_registered_attribution():
    real_sources = {
        job_discovery_service.PROVIDER_GREENHOUSE: GreenhouseJobSource.source_name,
    }

    # If a new provider is added to SUPPORTED_PROVIDERS, this mapping must
    # be extended - and its source must be registered for attribution.
    assert set(real_sources) | {job_discovery_service.PROVIDER_TEST_FIXTURE} == (
        job_discovery_service.SUPPORTED_PROVIDERS
    )
    for source_name in real_sources.values():
        assert get_source_attribution(source_name) is not None


def test_synthetic_sources_carry_no_attribution():
    assert get_source_attribution(TEST_FIXTURE_SOURCE) is None
    assert get_source_attribution(ExamplePagedSource.source_name) is None
    assert get_source_attribution(RESERVED_USER_SUBMITTED_SOURCE) is None


def test_no_real_provider_is_selected_by_default():
    from apps.api.config import Settings

    assert Settings.model_fields["job_discovery_provider"].default is None
    assert Settings.model_fields["job_discovery_greenhouse_board_token"].default is None
