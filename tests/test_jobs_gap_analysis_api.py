"""Authenticated API tests for Gap Analysis & Job-Specific Suggestions
(AJI-015): POST/GET /jobs/{job_id}/gap-analysis.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Company, Job, Preference, Profile, Resume, ResumeVersion, User
from apps.api.security import create_access_token
from apps.api.services.gap_analysis import service as gap_analysis_service
from apps.api.services.job_intelligence import service as job_intelligence_service
from apps.api.services.resume_fingerprint import compute_content_fingerprint


class FakeJobIntelligenceProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        return {}


class FakeGapAnalysisProvider:
    provider_name = "fake"
    model_name = "fake-model"
    calls_made = 0

    def generate_gap_suggestions(self, *, gap_candidates, job_context):
        FakeGapAnalysisProvider.calls_made += 1
        return {"gaps": []}


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fake_ai_providers(monkeypatch):
    monkeypatch.setattr(
        job_intelligence_service,
        "create_job_intelligence_provider",
        lambda: FakeJobIntelligenceProvider(),
    )
    FakeGapAnalysisProvider.calls_made = 0
    monkeypatch.setattr(
        gap_analysis_service,
        "create_gap_analysis_provider",
        lambda: FakeGapAnalysisProvider(),
    )


def _make_user(db, *, years_experience: float | None = 6.0) -> User:
    user = User(
        id=uuid4(),
        email=f"gap-api-{uuid4()}@example.com",
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
        name="Gap Analysis API Test Co",
        normalized_name="gap analysis api test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Senior Rust Engineer",
        location="Remote - United States",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="5+ years of Rust development required. SQL is a plus.",
        source="test",
        source_url="https://example.com/job/gap-1",
    )
    db.add(job)
    db.flush()

    return job


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_get_gap_analysis_requires_authentication(client, test_job):
    response = client.get(f"/jobs/{test_job.id}/gap-analysis")
    assert response.status_code == 401


def test_post_gap_analysis_requires_authentication(client, test_job):
    response = client.post(f"/jobs/{test_job.id}/gap-analysis")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

def test_get_gap_analysis_job_not_found(client, db):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{uuid4()}/gap-analysis",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_post_gap_analysis_job_not_found(client, db):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{uuid4()}/gap-analysis",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_get_gap_analysis_not_yet_generated(client, db, test_job):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{test_job.id}/gap-analysis",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert "not been generated" in response.json()["detail"]


def test_post_gap_analysis_no_resume_returns_404(client, db, test_job):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{test_job.id}/gap-analysis",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET must never invoke the AI provider
# ---------------------------------------------------------------------------

def test_get_gap_analysis_never_invokes_ai_provider(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Rust developer.")

    client.post(f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user))
    calls_after_post = FakeGapAnalysisProvider.calls_made
    assert calls_after_post >= 1

    client.get(f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user))

    assert FakeGapAnalysisProvider.calls_made == calls_after_post


# ---------------------------------------------------------------------------
# Happy path / response shape
# ---------------------------------------------------------------------------

def test_post_gap_analysis_generates_and_returns_shape(client, db, test_job):
    user = _make_user(db, years_experience=6.0)
    _make_resume_version(
        db,
        user=user,
        content_text="Senior engineer. Skills: SQL.",
    )

    response = client.post(
        f"/jobs/{test_job.id}/gap-analysis",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == str(test_job.id)
    assert data["ats_alignment_id"]
    assert data["job_intelligence_id"]
    assert data["generation_status"] in {"complete", "partial"}
    assert isinstance(data["must_have_gap_count"], int)
    assert isinstance(data["preferred_gap_count"], int)
    assert "gaps" in data

    for gap in data["gaps"]:
        assert gap["status"] in {"missing", "partial"}
        assert gap["suggestion_type"] in {
            "ADD_IF_TRUE",
            "REPHRASE_EXISTING",
            "HIGHLIGHT_EXISTING",
        }
        assert gap["confidence"] in {"high", "medium", "low"}
        if gap["status"] == "missing":
            assert gap["suggestion_type"] == "ADD_IF_TRUE"
            assert gap["resume_evidence"] is None


def test_get_gap_analysis_after_post_returns_same_record(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Rust developer.")

    post_response = client.post(
        f"/jobs/{test_job.id}/gap-analysis",
        headers=_auth_headers(user),
    )
    get_response = client.get(
        f"/jobs/{test_job.id}/gap-analysis",
        headers=_auth_headers(user),
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == post_response.json()["id"]


def test_post_gap_analysis_is_idempotent(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Rust developer.")

    first = client.post(
        f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user)
    )
    second = client.post(
        f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user)
    )

    assert first.json()["id"] == second.json()["id"]


# ---------------------------------------------------------------------------
# Security: user isolation
# ---------------------------------------------------------------------------

def test_gap_analysis_is_not_visible_to_other_users(client, db, test_job):
    user_a = _make_user(db)
    user_b = _make_user(db)

    _make_resume_version(db, user=user_a, content_text="Rust developer.")

    client.post(f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user_a))

    response_b = client.get(
        f"/jobs/{test_job.id}/gap-analysis",
        headers=_auth_headers(user_b),
    )

    assert response_b.status_code == 404


def test_different_users_get_independent_gap_analysis_results(client, db, test_job):
    user_a = _make_user(db)
    user_b = _make_user(db)

    _make_resume_version(db, user=user_a, content_text="Rust developer with Rust skills.")
    _make_resume_version(db, user=user_b, content_text="Marketing generalist.")

    response_a = client.post(
        f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user_a)
    )
    response_b = client.post(
        f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user_b)
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["id"] != response_b.json()["id"]


def test_gap_analysis_never_exposes_other_users_resume_data(client, db, test_job):
    user_a = _make_user(db)
    user_b = _make_user(db)

    _make_resume_version(
        db, user=user_a, content_text="Secret-project-alpha Rust developer."
    )
    _make_resume_version(db, user=user_b, content_text="Unrelated resume.")

    client.post(f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user_a))

    response = client.post(
        f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user_b)
    )

    assert "secret-project-alpha" not in str(response.json()).lower()


def test_public_jobs_listing_never_includes_gap_analysis(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Rust developer.")

    client.post(f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user))

    response = client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    job_payload = next(
        job for job in data["jobs"] if job["id"] == str(test_job.id)
    )

    assert "gap" not in job_payload
    assert "gaps" not in job_payload
    assert "must_have_gap_count" not in job_payload


# ---------------------------------------------------------------------------
# Resume version selection
# ---------------------------------------------------------------------------

def test_other_users_resume_version_id_is_rejected(client, db, test_job):
    owner = _make_user(db)
    intruder = _make_user(db)

    owners_version = _make_resume_version(
        db, user=owner, content_text="Rust developer."
    )

    response = client.post(
        f"/jobs/{test_job.id}/gap-analysis?resume_version_id={owners_version.id}",
        headers=_auth_headers(intruder),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Regression: ATS Alignment behavior is unaffected by Gap Analysis
# ---------------------------------------------------------------------------

def test_ats_endpoint_still_works_independently_of_gap_analysis(client, db, test_job):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Rust developer.")

    gap_response = client.post(
        f"/jobs/{test_job.id}/gap-analysis", headers=_auth_headers(user)
    )
    ats_response = client.get(
        f"/jobs/{test_job.id}/ats", headers=_auth_headers(user)
    )

    assert gap_response.status_code == 200
    assert ats_response.status_code == 200
    assert ats_response.json()["id"] == gap_response.json()["ats_alignment_id"]
