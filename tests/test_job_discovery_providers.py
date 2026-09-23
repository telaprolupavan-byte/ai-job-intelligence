"""AJI-024: provider contract, test-fixture provider, normalization and
validation rules. Pure / DB-free."""

import urllib.request

import pytest

from services.job_discovery.contracts import (
    RESERVED_USER_SUBMITTED_SOURCE,
    DiscoveredJob,
    RawProviderJob,
)
from services.job_discovery.deduplicator import build_job_fingerprint
from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
    normalize_url,
)
from services.job_discovery.pipeline import normalize_raw_jobs
from services.job_discovery.sources.greenhouse import GreenhouseJobSource
from services.job_discovery.sources.test_fixture import (
    TEST_FIXTURE_SOURCE,
    TestFixtureJobSource,
)
from services.job_discovery.validator import (
    JobValidationError,
    is_meaningful_description,
    validate_discovered_job,
)


def _normalized_fixture_jobs():
    source = TestFixtureJobSource()
    return normalize_raw_jobs(source, source.fetch_raw_jobs())


def _by_id(jobs, source_job_id):
    return next(job for job in jobs if job.source_job_id == source_job_id)


def _valid_job(**overrides) -> DiscoveredJob:
    fields = dict(
        source="greenhouse",
        source_job_id="1",
        title="Backend Engineer",
        company="Example Inc",
        description="Build and operate backend services.",
        requirements=None,
        responsibilities=None,
        location=None,
        country="USA",
        remote_type=None,
        employment_type=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        contract_duration=None,
        contract_worker_type=None,
        source_url=None,
        application_url=None,
        posted_at=None,
        expires_at=None,
    )
    fields.update(overrides)
    return DiscoveredJob(**fields)


# ---------------------------------------------------------------------------
# Provider contract / test-fixture provider
# ---------------------------------------------------------------------------


def test_fixture_provider_is_marked_as_test_provider():
    source = TestFixtureJobSource()

    assert source.is_test_provider is True
    assert source.source_name == TEST_FIXTURE_SOURCE
    assert GreenhouseJobSource.is_test_provider is False


def test_fixture_provider_output_is_deterministic():
    first, first_errors = _normalized_fixture_jobs()
    second, second_errors = _normalized_fixture_jobs()

    assert first == second
    assert [e.reason for e in first_errors] == [
        e.reason for e in second_errors
    ]


def test_fixture_raw_records_are_isolated_copies():
    source = TestFixtureJobSource()
    source.fetch_raw_jobs()[0].payload["title"] = "tampered"

    assert source.fetch_raw_jobs()[0].payload["title"] != "tampered"


def test_fixture_provider_includes_duplicates():
    jobs, _ = _normalized_fixture_jobs()
    fingerprints = [build_job_fingerprint(job) for job in jobs]

    assert len(fingerprints) != len(set(fingerprints))


def test_fixture_provider_malformed_record_is_a_normalization_rejection():
    jobs, errors = _normalized_fixture_jobs()

    assert len(TestFixtureJobSource().fetch_raw_jobs()) == 9
    assert len(jobs) == 8
    assert len(errors) == 1
    assert "Normalization failed" in errors[0].reason


def test_fixture_jobs_are_labelled_as_test_data_and_use_reserved_urls():
    jobs, _ = _normalized_fixture_jobs()

    for job in jobs:
        assert job.source == TEST_FIXTURE_SOURCE
        assert "test data" in job.company.lower()
        for url in (job.source_url, job.application_url):
            assert url is None or ".example/" in url


def test_fixture_includes_full_time_contract_remote_and_onsite_examples():
    jobs, _ = _normalized_fixture_jobs()

    assert {job.employment_type for job in jobs} >= {"full_time", "contract"}
    assert {job.remote_type for job in jobs} >= {"remote", "hybrid", "onsite"}


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def test_normalization_trims_title_and_keeps_line_structure():
    jobs, _ = _normalized_fixture_jobs()
    job = _by_id(jobs, "fx-1001")

    assert job.title == "Senior Backend Engineer"
    assert job.requirements == (
        "5+ years of Python.\nExperience with PostgreSQL."
    )
    assert job.responsibilities == "Build APIs.\nReview code."
    assert job.posted_at is not None


def test_normalization_maps_employment_and_remote_types():
    jobs, _ = _normalized_fixture_jobs()

    full_time = _by_id(jobs, "fx-1001")
    contract = _by_id(jobs, "fx-1002")

    assert full_time.employment_type == "full_time"
    assert full_time.remote_type == "hybrid"
    assert contract.employment_type == "contract"
    assert contract.remote_type == "remote"
    assert contract.contract_duration == "6 months"
    assert contract.contract_worker_type == "w2"
    assert contract.location == "Remote, United States"


def test_normalization_leaves_unknowns_unknown():
    jobs, _ = _normalized_fixture_jobs()

    unrecognized = _by_id(jobs, "fx-1003")
    assert unrecognized.employment_type is None  # "Gig" is not guessed
    assert unrecognized.salary_min is None
    assert unrecognized.salary_max is None

    sparse = next(job for job in jobs if job.source_job_id is None)
    assert sparse.location is None
    assert sparse.remote_type is None
    assert sparse.employment_type is None
    assert sparse.source_url is None
    assert sparse.posted_at is None


def test_unsafe_urls_are_dropped_not_stored():
    jobs, _ = _normalized_fixture_jobs()

    assert _by_id(jobs, "fx-1003").application_url is None
    assert normalize_url("javascript:alert(1)") is None
    assert normalize_url("data:text/html,hi") is None
    assert normalize_url("/relative/path") is None
    assert normalize_url("https://") is None
    assert normalize_url(" HTTPS://jobs.example/1 ") == "HTTPS://jobs.example/1"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Full-Time", "full_time"),
        ("contractor", "contract"),
        ("Part Time", "part_time"),
        ("Gig", None),
        (None, None),
    ],
)
def test_employment_type_normalization(value, expected):
    assert normalize_employment_type(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Fully Remote", "remote"),
        ("Hybrid", "hybrid"),
        ("On-site", "onsite"),
        ("Sometimes", None),
    ],
)
def test_remote_type_normalization(value, expected):
    assert normalize_remote_type(value) == expected


def test_greenhouse_malformed_record_is_isolated(monkeypatch):
    """Before AJI-024 a Greenhouse record without an `id` raised KeyError
    out of fetch_jobs() and failed the whole run."""
    source = GreenhouseJobSource(board_token="example", company_name="Ex")
    raw = [
        RawProviderJob(source="greenhouse", payload={"title": "No id"}),
        RawProviderJob(
            source="greenhouse",
            payload={
                "id": 7,
                "title": "Engineer",
                "location": {"name": "Austin, TX"},
                "content": "<p>Build reliable services.</p>",
                "absolute_url": "javascript:alert(1)",
            },
        ),
    ]

    jobs, errors = normalize_raw_jobs(source, raw)

    assert len(errors) == 1
    assert "missing its id" in errors[0].reason
    assert jobs[0].source_job_id == "7"
    assert jobs[0].source_url is None
    assert jobs[0].application_url is None


def test_greenhouse_fetch_raw_jobs_wraps_payload(monkeypatch):
    class _Response:
        def read(self):
            return b'{"jobs": [{"id": 1, "title": "A"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda request, timeout=None: _Response()
    )

    raw = GreenhouseJobSource(
        board_token="example", company_name="Ex"
    ).fetch_raw_jobs()

    assert raw == [
        RawProviderJob(source="greenhouse", payload={"id": 1, "title": "A"})
    ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_required_fields_are_enforced():
    for field in ("title", "company", "description", "source"):
        with pytest.raises(JobValidationError, match=field):
            validate_discovered_job(_valid_job(**{field: ""}))


def test_optional_fields_do_not_invalidate():
    validate_discovered_job(_valid_job())


@pytest.mark.parametrize(
    "description", ["TBD", "n/a", "See link.", "-", "Short one"]
)
def test_placeholder_or_trivial_description_is_rejected(description):
    assert not is_meaningful_description(description)

    with pytest.raises(JobValidationError, match="Description"):
        validate_discovered_job(_valid_job(description=description))


def test_discovery_cannot_use_the_user_submitted_source():
    with pytest.raises(JobValidationError, match="reserved"):
        validate_discovered_job(
            _valid_job(source=RESERVED_USER_SUBMITTED_SOURCE)
        )


# ---------------------------------------------------------------------------
# Deduplication identity (existing fingerprint architecture, reused)
# ---------------------------------------------------------------------------


def test_same_provider_same_job_shares_identity():
    assert build_job_fingerprint(_valid_job()) == build_job_fingerprint(
        _valid_job(title="Renamed")
    )


def test_distinct_jobs_have_distinct_identity():
    assert build_job_fingerprint(_valid_job()) != build_job_fingerprint(
        _valid_job(source_job_id="2")
    )
    assert build_job_fingerprint(_valid_job()) != build_job_fingerprint(
        _valid_job(source="other_provider")
    )
