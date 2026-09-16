from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.deduplicator import build_job_fingerprint


def make_job(**overrides) -> DiscoveredJob:
    values = {
        "source": "greenhouse",
        "source_job_id": "12345",
        "title": "Machine Learning Engineer",
        "company": "Example AI",
        "description": "Build machine learning systems.",
        "requirements": "Python, PyTorch",
        "responsibilities": "Develop ML systems.",
        "location": "New York, NY",
        "country": "USA",
        "remote_type": "hybrid",
        "employment_type": "full_time",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "contract_duration": None,
        "contract_worker_type": None,
        "source_url": "https://example.com/job/12345",
        "application_url": "https://example.com/apply/12345",
        "posted_at": None,
        "expires_at": None,
    }

    values.update(overrides)
    return DiscoveredJob(**values)


def test_same_source_id_produces_same_fingerprint():
    job1 = make_job()
    job2 = make_job()

    assert build_job_fingerprint(job1) == build_job_fingerprint(job2)


def test_different_source_id_produces_different_fingerprint():
    job1 = make_job(source_job_id="12345")
    job2 = make_job(source_job_id="67890")

    assert build_job_fingerprint(job1) != build_job_fingerprint(job2)


def test_fallback_fingerprint_without_source_id():
    job1 = make_job(source_job_id=None)
    job2 = make_job(source_job_id=None)

    assert build_job_fingerprint(job1) == build_job_fingerprint(job2)


def test_fallback_changes_when_job_identity_changes():
    job1 = make_job(
        source_job_id=None,
        title="Machine Learning Engineer",
    )

    job2 = make_job(
        source_job_id=None,
        title="Senior Machine Learning Engineer",
    )

    assert build_job_fingerprint(job1) != build_job_fingerprint(job2)


def test_fingerprint_is_stable():
    job = make_job()

    first = build_job_fingerprint(job)
    second = build_job_fingerprint(job)

    assert first == second
    assert len(first) == 64