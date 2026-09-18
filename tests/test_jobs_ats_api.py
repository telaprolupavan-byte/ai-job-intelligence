"""Authenticated API tests for ATS Alignment (AJI-013): POST/GET
/jobs/{job_id}/ats.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Company, Job, Preference, Profile, Resume, ResumeVersion, User
from apps.api.security import create_access_token
from apps.api.services.job_intelligence import service as job_intelligence_service
from apps.api.services.resume_fingerprint import compute_content_fingerprint


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        return {}


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
        job_intelligence_service,
        "create_job_intelligence_provider",
        lambda: FakeProvider(),
    )


def _make_user(db, *, years_experience: float | None = 6.0) -> User:
    user = User(
        id=uuid4(),
        email=f"ats-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id, years_experience=years_experience))
    db.add(Preference(id=uuid4(), user_id=user.id))
    db.flush()

    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _make_resume_version(db, *, user: User, content_text: str) -> ResumeVersion:
    resume = Resume(
        id=uuid4(),
        user_id=user.id,
        filename="resume.txt",
        original_text=content_text,
    )
    db.add(resume)
    db.flush()

    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name="resume",
        content_text=content_text,
        content_fingerprint=compute_content_fingerprint(content_text),
        original_filename="resume.txt",
        storage_path=f"/tmp/{uuid4()}.txt",
        is_master=True,
    )
    db.add(version)
    db.flush()

    return version


@pytest.fixture
def test_job(db) -> Job:
    company = Company(
        id=uuid4(),
        name="ATS API Test Co",
        normalized_name="ats api test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Senior Python Engineer",
        location="Remote - United States",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="5+ years of Python development required.",
        source="test",
        source_url="https://example.com/job/ats-1",
    )
    db.add(job)
    db.flush()

    return job


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_get_ats_requires_authentication(client, test_job):
    response = client.get(f"/jobs/{test_job.id}/ats")
    assert response.status_code == 401


def test_post_ats_requires_authentication(client, test_job):
    response = client.post(f"/jobs/{test_job.id}/ats")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

def test_get_ats_job_not_found(client, db):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{uuid4()}/ats",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_post_ats_job_not_found(client, db):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{uuid4()}/ats",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_get_ats_not_yet_generated(client, db, test_job):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{test_job.id}/ats",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert "not been generated" in response.json()["detail"]


def test_post_ats_no_resume_returns_404(client, db, test_job):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{test_job.id}/ats",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Happy path / response shape
# ---------------------------------------------------------------------------

def test_post_ats_generates_and_returns_shape(client, db, test_job):
    user = _make_user(db, years_experience=6.0)
    _make_resume_version(
        db,
        user=user,
        content_text="Senior engineer. 6 years of Python experience. Skills: Python.",
    )

    response = client.post(
        f"/jobs/{test_job.id}/ats",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == str(test_job.id)
    assert data["engine_version"]
    assert isinstance(data["overall_score"], (int, float))
    assert data["confidence"] in {"high", "medium", "low"}
    assert "requirement_results" in data
    assert len(data["requirement_results"]) >= 1

    for item in data["requirement_results"]:
        assert item["status"] in {"matched", "partial", "missing"}
        assert item["category"] in {"must_have", "preferred"}
        assert item["confidence"] in {"high", "medium", "low"}
        assert isinstance(item["hard_requirement"], bool)
        assert isinstance(item["ambiguous"], bool)

    # AJI-020C: ATS Alignment now sources from, and is traceable back to,
    # a Requirement Intelligence snapshot; relationships/screening
    # constraints are exposed (descriptive-only) on the same response.
    assert data["requirement_intelligence_id"]
    assert "relationships" in data
    assert "screening_constraints" in data

    # AJI-020: the weighted score breakdown is part of the response shape.
    assert len(data["score_components"]) == 4
    component_names = {component["name"] for component in data["score_components"]}
    assert component_names == {
        "requirement_coverage",
        "keyword_terminology_alignment",
        "resume_evidence_experience",
        "structure_parseability",
    }
    for component in data["score_components"]:
        assert 0.0 <= component["score"] <= 100.0
    assert 0.0 <= data["overall_score"] <= 100.0
    assert data["must_have_ceiling"] is None or (
        0.0 <= data["must_have_ceiling"] <= 100.0
    )


def test_get_ats_after_post_returns_same_record(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    post_response = client.post(
        f"/jobs/{test_job.id}/ats",
        headers=_auth_headers(user),
    )
    get_response = client.get(
        f"/jobs/{test_job.id}/ats",
        headers=_auth_headers(user),
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == post_response.json()["id"]


def test_post_ats_is_idempotent(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    first = client.post(f"/jobs/{test_job.id}/ats", headers=_auth_headers(user))
    second = client.post(f"/jobs/{test_job.id}/ats", headers=_auth_headers(user))

    assert first.json()["id"] == second.json()["id"]


# ---------------------------------------------------------------------------
# Security: user isolation, never shared like Job Intelligence
# ---------------------------------------------------------------------------

def test_ats_alignment_is_not_visible_to_other_users(client, db, test_job):
    user_a = _make_user(db)
    user_b = _make_user(db)

    _make_resume_version(db, user=user_a, content_text="Python developer.")

    client.post(f"/jobs/{test_job.id}/ats", headers=_auth_headers(user_a))

    response_b = client.get(
        f"/jobs/{test_job.id}/ats",
        headers=_auth_headers(user_b),
    )

    assert response_b.status_code == 404


def test_different_users_get_independent_ats_results(client, db, test_job):
    user_a = _make_user(db)
    user_b = _make_user(db)

    _make_resume_version(
        db, user=user_a, content_text="Python developer with Python skills."
    )
    _make_resume_version(db, user=user_b, content_text="Marketing generalist.")

    response_a = client.post(
        f"/jobs/{test_job.id}/ats", headers=_auth_headers(user_a)
    )
    response_b = client.post(
        f"/jobs/{test_job.id}/ats", headers=_auth_headers(user_b)
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["id"] != response_b.json()["id"]


def test_ats_alignment_never_exposes_other_users_resume_data(client, db, test_job):
    user_a = _make_user(db)
    user_b = _make_user(db)

    _make_resume_version(
        db, user=user_a, content_text="Secret-project-alpha Python developer."
    )
    _make_resume_version(db, user=user_b, content_text="Unrelated resume.")

    client.post(f"/jobs/{test_job.id}/ats", headers=_auth_headers(user_a))

    response = client.post(
        f"/jobs/{test_job.id}/ats", headers=_auth_headers(user_b)
    )

    assert "secret-project-alpha" not in str(response.json()).lower()


def test_public_jobs_listing_never_includes_ats_alignment(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    client.post(f"/jobs/{test_job.id}/ats", headers=_auth_headers(user))

    response = client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    job_payload = next(
        job for job in data["jobs"] if job["id"] == str(test_job.id)
    )

    assert "ats" not in job_payload
    assert "overall_score" not in job_payload


# ---------------------------------------------------------------------------
# Resume version selection
# ---------------------------------------------------------------------------

def test_other_users_resume_version_id_is_rejected(client, db, test_job):
    owner = _make_user(db)
    intruder = _make_user(db)

    owners_version = _make_resume_version(
        db, user=owner, content_text="Python developer."
    )

    response = client.post(
        f"/jobs/{test_job.id}/ats?resume_version_id={owners_version.id}",
        headers=_auth_headers(intruder),
    )

    assert response.status_code == 404
