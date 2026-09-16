import uuid

from apps.api.models import Company, Job
from apps.api.routers.jobs import list_jobs


def create_job(
    db,
    *,
    title,
    company_name,
    employment_type="full_time",
    remote_type="remote",
    location="New York, NY",
    is_active=True,
):
    unique_id = uuid.uuid4()

    company = Company(
        name=f"{company_name} {unique_id}",
        normalized_name=f"{company_name.lower()}-{unique_id}",
    )

    db.add(company)
    db.flush()

    job = Job(
        company_id=company.id,
        title=title,
        location=location,
        country="USA",
        remote_type=remote_type,
        employment_type=employment_type,
        salary_min=100000,
        salary_max=150000,
        salary_currency="USD",
        contract_duration=None,
        contract_worker_type=None,
        description=f"{title} job description",
        requirements="Python, SQL, Machine Learning",
        responsibilities="Build and maintain AI/ML systems",
        posting_date=None,
        source="test",
        source_url=f"https://example.com/jobs/{unique_id}",
        application_url=f"https://example.com/apply/{unique_id}",
        external_job_id=f"test-{unique_id}",
        is_active=is_active,
    )

    db.add(job)
    db.flush()
    db.refresh(job)

    return job


def test_list_jobs_empty(db):
    result = list_jobs(
        db=db,
        search="this-job-definitely-does-not-exist",
        employment_type=None,
        remote_type=None,
        location=None,
        page=1,
        page_size=20,
    )

    assert result["jobs"] == []
    assert result["pagination"]["total"] == 0


def test_create_active_job(db):
    job = create_job(
        db,
        title="AI Engineer",
        company_name="Test AI Company",
    )

    assert job.id is not None
    assert job.title == "AI Engineer"
    assert job.is_active is True


def test_create_inactive_job(db):
    job = create_job(
        db,
        title="Inactive AI Engineer",
        company_name="Inactive Test Company",
        is_active=False,
    )

    assert job.id is not None
    assert job.is_active is False


def test_job_title_search(db):
    unique_id = uuid.uuid4()

    ai_job = create_job(
        db,
        title=f"Machine Learning Engineer {unique_id}",
        company_name=f"Alpha AI {unique_id}",
    )

    other_job = create_job(
        db,
        title=f"Frontend Developer {unique_id}",
        company_name=f"Beta Software {unique_id}",
    )

    result = list_jobs(
        db=db,
        search=f"Machine Learning Engineer {unique_id}",
        employment_type=None,
        remote_type=None,
        location=None,
        page=1,
        page_size=20,
    )

    job_ids = {job["id"] for job in result["jobs"]}

    assert str(ai_job.id) in job_ids
    assert str(other_job.id) not in job_ids


def test_company_search(db):
    unique_id = uuid.uuid4()

    target_job = create_job(
        db,
        title=f"AI Engineer {unique_id}",
        company_name=f"OpenAI Test Company {unique_id}",
    )

    other_job = create_job(
        db,
        title=f"AI Engineer Other {unique_id}",
        company_name=f"Other Test Company {unique_id}",
    )

    result = list_jobs(
        db=db,
        search=f"OpenAI Test Company {unique_id}",
        employment_type=None,
        remote_type=None,
        location=None,
        page=1,
        page_size=20,
    )

    job_ids = {job["id"] for job in result["jobs"]}

    assert str(target_job.id) in job_ids
    assert str(other_job.id) not in job_ids


def test_employment_type_filter(db):
    unique_id = uuid.uuid4()

    full_time_job = create_job(
        db,
        title=f"Full Time AI Engineer {unique_id}",
        company_name=f"Full Time Company {unique_id}",
        employment_type="full_time",
    )

    contract_job = create_job(
        db,
        title=f"Contract AI Engineer {unique_id}",
        company_name=f"Contract Company {unique_id}",
        employment_type="contract",
    )

    result = list_jobs(
        db=db,
        search=f"AI Engineer {unique_id}",
        employment_type="contract",
        remote_type=None,
        location=None,
        page=1,
        page_size=100,
    )

    job_ids = {job["id"] for job in result["jobs"]}

    assert str(contract_job.id) in job_ids
    assert str(full_time_job.id) not in job_ids


def test_remote_type_filter(db):
    unique_id = uuid.uuid4()

    remote_job = create_job(
        db,
        title=f"Remote AI Engineer {unique_id}",
        company_name=f"Remote Company {unique_id}",
        remote_type="remote",
    )

    onsite_job = create_job(
        db,
        title=f"Onsite AI Engineer {unique_id}",
        company_name=f"Onsite Company {unique_id}",
        remote_type="onsite",
    )

    result = list_jobs(
        db=db,
        search=f"AI Engineer {unique_id}",
        employment_type=None,
        remote_type="remote",
        location=None,
        page=1,
        page_size=20,
    )

    job_ids = {job["id"] for job in result["jobs"]}

    assert str(remote_job.id) in job_ids
    assert str(onsite_job.id) not in job_ids


def test_location_filter(db):
    unique_id = uuid.uuid4()

    new_york_job = create_job(
        db,
        title=f"New York AI Engineer {unique_id}",
        company_name=f"NY Test Company {unique_id}",
        location=f"New York, NY {unique_id}",
    )

    california_job = create_job(
        db,
        title=f"California AI Engineer {unique_id}",
        company_name=f"CA Test Company {unique_id}",
        location=f"San Francisco, CA {unique_id}",
    )

    result = list_jobs(
        db=db,
        search=f"AI Engineer {unique_id}",
        employment_type=None,
        remote_type=None,
        location=f"New York, NY {unique_id}",
        page=1,
        page_size=20,
    )

    job_ids = {job["id"] for job in result["jobs"]}

    assert str(new_york_job.id) in job_ids
    assert str(california_job.id) not in job_ids


def test_inactive_jobs_are_excluded(db):
    unique_id = uuid.uuid4()

    active_job = create_job(
        db,
        title=f"Active AI Engineer {unique_id}",
        company_name=f"Active Company {unique_id}",
    )

    inactive_job = create_job(
        db,
        title=f"Inactive AI Engineer {unique_id}",
        company_name=f"Inactive Company {unique_id}",
        is_active=False,
    )

    result = list_jobs(
        db=db,
        search=f"AI Engineer {unique_id}",
        employment_type=None,
        remote_type=None,
        location=None,
        page=1,
        page_size=20,
    )

    job_ids = {job["id"] for job in result["jobs"]}

    assert str(active_job.id) in job_ids
    assert str(inactive_job.id) not in job_ids


def test_pagination(db):
    unique_id = uuid.uuid4()

    for index in range(5):
        create_job(
            db,
            title=f"Pagination AI Engineer {unique_id} {index}",
            company_name=f"Pagination Company {unique_id} {index}",
        )

    result = list_jobs(
        db=db,
        search=f"Pagination AI Engineer {unique_id}",
        employment_type=None,
        remote_type=None,
        location=None,
        page=1,
        page_size=2,
    )

    assert result["pagination"]["page"] == 1
    assert result["pagination"]["page_size"] == 2
    assert result["pagination"]["total"] == 5
    assert len(result["jobs"]) == 2

    second_page = list_jobs(
        db=db,
        search=f"Pagination AI Engineer {unique_id}",
        employment_type=None,
        remote_type=None,
        location=None,
        page=2,
        page_size=2,
    )

    first_page_ids = {job["id"] for job in result["jobs"]}
    second_page_ids = {job["id"] for job in second_page["jobs"]}

    assert first_page_ids.isdisjoint(second_page_ids)
