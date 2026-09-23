import pytest

from services.job_discovery.contracts import DiscoveredJob
from services.job_discovery.validator import (
    JobValidationError,
    validate_discovered_job,
)


def make_valid_job() -> DiscoveredJob:
    return DiscoveredJob(
        source="greenhouse",
        source_job_id="12345",
        title="Machine Learning Engineer",
        company="Example AI",
        description="Build and deploy machine learning systems.",
        requirements="Python, PyTorch, SQL",
        responsibilities="Develop and maintain ML systems.",
        location="New York, NY",
        country="USA",
        remote_type="hybrid",
        employment_type="full_time",
        salary_min=120000,
        salary_max=160000,
        salary_currency="USD",
        contract_duration=None,
        contract_worker_type=None,
        source_url="https://example.com/jobs/12345",
        application_url="https://example.com/apply/12345",
        posted_at=None,
        expires_at=None,
    )


def test_valid_job_passes_validation():
    job = make_valid_job()

    validate_discovered_job(job)


def test_missing_title_fails_validation():
    job = make_valid_job()
    job.title = ""

    with pytest.raises(JobValidationError, match="title"):
        validate_discovered_job(job)


def test_missing_company_fails_validation():
    job = make_valid_job()
    job.company = ""

    with pytest.raises(JobValidationError, match="company"):
        validate_discovered_job(job)


def test_missing_description_fails_validation():
    job = make_valid_job()
    job.description = None

    with pytest.raises(JobValidationError, match="description"):
        validate_discovered_job(job)


def test_missing_source_and_application_urls_are_optional():
    """AJI-024: a URL is recorded "where available" - its absence alone
    never invalidates an otherwise valid job."""
    job = make_valid_job()
    job.source_url = None
    job.application_url = None

    validate_discovered_job(job)


def test_non_us_job_fails_validation():
    job = make_valid_job()
    job.country = "Canada"

    with pytest.raises(
        JobValidationError,
        match="United States",
    ):
        validate_discovered_job(job)


def test_optional_fields_can_be_missing():
    job = make_valid_job()

    job.location = None
    job.remote_type = None
    job.employment_type = None
    job.salary_min = None
    job.salary_max = None
    job.salary_currency = None

    validate_discovered_job(job)