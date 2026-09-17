from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.models import Company, Job, Preference, Profile, User
from apps.api.security import create_access_token
from apps.api.dependencies import get_db


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _make_user(db, **preference_kwargs):
    user = User(
        id=uuid4(),
        email=f"eligibility-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id))

    if preference_kwargs:
        db.add(Preference(id=uuid4(), user_id=user.id, **preference_kwargs))

    db.flush()

    return user


def _auth_headers(user):
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_job(db):
    company = Company(
        id=uuid4(),
        name="Eligibility API Test Co",
        normalized_name="eligibility api test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Backend Engineer",
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="Build backend services.",
        source="test",
    )
    db.add(job)
    db.flush()

    return job


def test_get_job_eligibility_requires_authentication(client, test_job):
    response = client.get(f"/jobs/{test_job.id}/eligibility")

    assert response.status_code == 401


def test_get_job_eligibility_job_not_found(client, db):
    user = _make_user(db)
    missing_job_id = uuid4()

    response = client.get(
        f"/jobs/{missing_job_id}/eligibility",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_get_job_eligibility_eligible_response_shape(client, db, test_job):
    user = _make_user(db, employment_types=["full_time"])

    response = client.get(
        f"/jobs/{test_job.id}/eligibility",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == str(test_job.id)
    assert data["status"] == "eligible"
    assert data["failed_constraints"] == []
    assert isinstance(data["checks"], list)
    assert any(
        check["constraint"] == "employment_type" and check["status"] == "pass"
        for check in data["checks"]
    )


def test_get_job_eligibility_hard_constraint_beats_would_be_high_match(
    client, db, test_job,
):
    # Contract-only user against a Full-Time job must be INELIGIBLE
    # regardless of anything else about the job.
    user = _make_user(db, employment_types=["contract"])

    response = client.get(
        f"/jobs/{test_job.id}/eligibility",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ineligible"
    assert "employment_type" in data["failed_constraints"]


def test_user_a_cannot_influence_user_b_eligibility(client, db, test_job):
    contract_only_user = _make_user(db, employment_types=["contract"])
    unrestricted_user = _make_user(db)

    contract_response = client.get(
        f"/jobs/{test_job.id}/eligibility",
        headers=_auth_headers(contract_only_user),
    )
    unrestricted_response = client.get(
        f"/jobs/{test_job.id}/eligibility",
        headers=_auth_headers(unrestricted_user),
    )

    assert contract_response.json()["status"] == "ineligible"
    assert unrestricted_response.json()["status"] == "eligible"


def test_public_jobs_listing_never_includes_eligibility_fields(
    client, db, test_job,
):
    response = client.get("/jobs")

    assert response.status_code == 200

    data = response.json()

    job_payload = next(
        job for job in data["jobs"] if job["id"] == str(test_job.id)
    )

    assert "status" not in job_payload
    assert "eligibility" not in job_payload
    assert "checks" not in job_payload
    assert "failed_constraints" not in job_payload
