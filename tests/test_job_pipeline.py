import uuid

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.pipeline import run_discovery_pipeline


def make_job(**overrides) -> DiscoveredJob:
    unique_id = uuid.uuid4()

    values = {
        "source": "greenhouse",
        "source_job_id": str(unique_id),
        "title": "Machine Learning Engineer",
        "company": "Pipeline Test AI",
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
        "source_url": f"https://example.com/job/{unique_id}",
        "application_url": f"https://example.com/apply/{unique_id}",
        "posted_at": None,
        "expires_at": None,
    }

    values.update(overrides)
    return DiscoveredJob(**values)


def test_valid_jobs_are_inserted(db):
    jobs = [make_job(), make_job()]

    result = run_discovery_pipeline(db, jobs)

    assert len(result.inserted) == 2
    assert len(result.updated) == 0
    assert len(result.rejected) == 0
    assert len(result.accepted) == 2


def test_invalid_job_is_rejected_without_stopping_batch(db):
    good_job = make_job()
    bad_job = make_job(title="")

    result = run_discovery_pipeline(db, [good_job, bad_job])

    assert len(result.inserted) == 1
    assert len(result.rejected) == 1
    assert "title" in result.rejected[0].reason


def test_repeated_ingestion_updates_existing_job(db):
    job = make_job()

    first_result = run_discovery_pipeline(db, [job])

    updated_job = make_job(
        source_job_id=job.source_job_id,
        title="Senior Machine Learning Engineer",
    )

    second_result = run_discovery_pipeline(db, [updated_job])

    assert len(first_result.inserted) == 1
    assert len(second_result.updated) == 1
    assert len(second_result.inserted) == 0
    assert second_result.updated[0].id == first_result.inserted[0].id
    assert second_result.updated[0].title == "Senior Machine Learning Engineer"


def test_mixed_batch_reports_all_outcomes(db):
    existing_job = make_job()
    run_discovery_pipeline(db, [existing_job])

    repeat_job = make_job(
        source_job_id=existing_job.source_job_id,
        title="Updated Title",
    )
    new_job = make_job()
    invalid_job = make_job(company="")

    result = run_discovery_pipeline(db, [repeat_job, new_job, invalid_job])

    assert len(result.updated) == 1
    assert len(result.inserted) == 1
    assert len(result.rejected) == 1
    assert "company" in result.rejected[0].reason
