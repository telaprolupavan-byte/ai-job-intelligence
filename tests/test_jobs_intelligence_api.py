from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Company, Job, User
from apps.api.security import create_access_token
from apps.api.services.job_intelligence import service


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        return {
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": raw_jd_text.split("\n")[0],
            "normalized_title_confidence": "high",
        }


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fake_ai_provider(monkeypatch):
    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: FakeProvider()
    )


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"job-intel-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_job(db) -> Job:
    company = Company(
        id=uuid4(),
        name="Job Intelligence API Test Co",
        normalized_name="job intelligence api test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Senior AI Engineer",
        location="Remote - United States",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description=(
            "3+ years of Python development required. PyTorch preferred."
        ),
        source="test",
        source_url="https://example.com/job/1",
    )
    db.add(job)
    db.flush()

    return job


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_get_job_intelligence_requires_authentication(client, test_job):
    response = client.get(f"/jobs/{test_job.id}/intelligence")
    assert response.status_code == 401


def test_post_job_intelligence_requires_authentication(client, test_job):
    response = client.post(f"/jobs/{test_job.id}/intelligence")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

def test_get_job_intelligence_job_not_found(client, db):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{uuid4()}/intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_post_job_intelligence_job_not_found(client, db):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{uuid4()}/intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_get_job_intelligence_not_yet_generated(client, db, test_job):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert "not been generated" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Happy path / response shape
# ---------------------------------------------------------------------------

def test_post_job_intelligence_generates_and_returns_shape(client, db, test_job):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == str(test_job.id)
    assert data["analysis_version"]
    assert data["analyzer_version"]
    assert data["prompt_version"]
    assert data["extraction_status"] == "complete"

    intelligence = data["intelligence"]
    assert intelligence["identity"]["original_title"] == "Senior AI Engineer"

    required_skills = {
        item["canonical_skill"] for item in intelligence["required_skills"]
    }
    preferred_skills = {
        item["canonical_skill"] for item in intelligence["preferred_skills"]
    }
    assert "python" in required_skills
    assert "pytorch" in preferred_skills


def test_get_job_intelligence_after_post_returns_same_snapshot(
    client, db, test_job
):
    user = _make_user(db)

    post_response = client.post(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )
    get_response = client.get(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == post_response.json()["id"]


def test_post_job_intelligence_is_idempotent(client, db, test_job):
    user = _make_user(db)

    first = client.post(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )
    second = client.post(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )

    assert first.json()["id"] == second.json()["id"]


# ---------------------------------------------------------------------------
# Security: shared data, never personalized leakage
# ---------------------------------------------------------------------------

def test_job_intelligence_shared_across_users(client, db, test_job):
    user_a = _make_user(db)
    user_b = _make_user(db)

    generated = client.post(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user_a),
    )

    fetched_by_b = client.get(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user_b),
    )

    assert fetched_by_b.status_code == 200
    assert fetched_by_b.json()["id"] == generated.json()["id"]


def test_job_intelligence_never_exposes_personalized_fields(
    client, db, test_job
):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )

    payload = response.json()
    serialized = str(payload).lower()

    # Job Intelligence is shared, job-scoped data; it must never carry
    # user-specific eligibility, Job Match, or ATS Alignment fields.
    assert "eligibility" not in serialized
    assert "job_match" not in serialized
    assert "ats_score" not in serialized
    assert "user_id" not in payload
    assert "resume" not in serialized


def test_public_jobs_listing_never_includes_job_intelligence(
    client, db, test_job
):
    user = _make_user(db)

    client.post(
        f"/jobs/{test_job.id}/intelligence",
        headers=_auth_headers(user),
    )

    response = client.get("/jobs")

    assert response.status_code == 200

    data = response.json()
    job_payload = next(
        job for job in data["jobs"] if job["id"] == str(test_job.id)
    )

    assert "intelligence" not in job_payload
    assert "required_skills" not in job_payload
