"""Authenticated API tests for Requirement Intelligence (AJI-020B):
POST/GET /jobs/{job_id}/requirement-intelligence.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Company, Job, User
from apps.api.security import create_access_token
from apps.api.services.requirement_intelligence import (
    persistence_service as requirement_intelligence_persistence_service,
)
from apps.api.services.requirement_intelligence import (
    service as requirement_intelligence_service,
)


class FakeProvider:
    provider_name = "openai"

    def __init__(self, *, model_name: str) -> None:
        self.model_name = model_name

    def generate_requirement_semantics(self, *, raw_jd_text, deterministic_context):
        return {
            "normalized_title": "Backend Engineer",
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
        requirement_intelligence_service,
        "create_requirement_intelligence_provider",
        lambda: FakeProvider(
            model_name=requirement_intelligence_persistence_service.settings.ai_model
        ),
    )


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"req-intel-api-{uuid4()}@example.com",
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
        name="Requirement Intelligence API Test Co",
        normalized_name="requirement intelligence api test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Senior Backend Engineer",
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="5+ years of Python experience required.",
        source="test",
        source_url="https://example.com/job/req-intel-1",
    )
    db.add(job)
    db.flush()

    return job


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_get_requirement_intelligence_requires_authentication(client, test_job):
    response = client.get(f"/jobs/{test_job.id}/requirement-intelligence")
    assert response.status_code == 401


def test_post_requirement_intelligence_requires_authentication(client, test_job):
    response = client.post(f"/jobs/{test_job.id}/requirement-intelligence")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Not found / not yet generated
# ---------------------------------------------------------------------------

def test_get_requirement_intelligence_job_not_found(client, db):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{uuid4()}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_post_requirement_intelligence_job_not_found(client, db):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{uuid4()}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_get_requirement_intelligence_not_yet_generated(client, db, test_job):
    user = _make_user(db)

    response = client.get(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404
    assert "not been generated" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Happy path / response shape
# ---------------------------------------------------------------------------

def test_post_requirement_intelligence_generates_and_returns_shape(
    client, db, test_job
):
    user = _make_user(db)

    response = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()
    assert data["job_id"] == str(test_job.id)
    assert data["analysis_version"]
    assert data["analyzer_version"]
    assert data["prompt_version"]
    assert data["extraction_status"] in {"complete", "partial"}
    assert "intelligence" in data

    intelligence = data["intelligence"]
    assert intelligence["identity"]["original_title"] == test_job.title
    assert any(
        item["requirement_type"] == "skill" and "python" in item["canonical_terms"]
        for item in intelligence["requirements"]
    )


def test_get_requirement_intelligence_after_post_returns_same_record(
    client, db, test_job
):
    user = _make_user(db)

    post_response = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )
    get_response = client.get(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == post_response.json()["id"]


def test_post_requirement_intelligence_is_idempotent(client, db, test_job):
    user = _make_user(db)

    first = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )
    second = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert first.json()["id"] == second.json()["id"]


# ---------------------------------------------------------------------------
# Security: user isolation
# ---------------------------------------------------------------------------

def test_requirement_intelligence_is_not_visible_to_other_users(
    client, db, test_job
):
    user_a = _make_user(db)
    user_b = _make_user(db)

    client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user_a),
    )

    response_b = client.get(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user_b),
    )

    assert response_b.status_code == 404


def test_different_users_get_independent_requirement_intelligence_records(
    client, db, test_job
):
    user_a = _make_user(db)
    user_b = _make_user(db)

    response_a = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user_a),
    )
    response_b = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user_b),
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["id"] != response_b.json()["id"]

    # Each user only ever sees their own snapshot on GET.
    get_a = client.get(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user_a),
    )
    get_b = client.get(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user_b),
    )
    assert get_a.json()["id"] == response_a.json()["id"]
    assert get_b.json()["id"] == response_b.json()["id"]


def test_public_jobs_listing_never_includes_requirement_intelligence(
    client, db, test_job
):
    user = _make_user(db)

    client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    response = client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    job_payload = next(
        job for job in data["jobs"] if job["id"] == str(test_job.id)
    )

    assert "requirement_intelligence" not in job_payload
    assert "intelligence" not in job_payload


# ---------------------------------------------------------------------------
# Provider/service failure handling
# ---------------------------------------------------------------------------

def test_post_requirement_intelligence_degrades_to_partial_on_provider_failure(
    client, db, test_job, monkeypatch
):
    from apps.api.services.requirement_intelligence.providers.openai_provider import (
        RequirementIntelligenceProviderError,
    )

    def _raise():
        raise RequirementIntelligenceProviderError("provider unavailable")

    monkeypatch.setattr(
        requirement_intelligence_service,
        "create_requirement_intelligence_provider",
        _raise,
    )

    user = _make_user(db)

    response = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["extraction_status"] == "partial"
    assert data["model_provider"] is None
    # Deterministic requirements still present despite the AI failure.
    assert any(
        item["requirement_type"] == "skill"
        for item in data["intelligence"]["requirements"]
    )


def test_post_requirement_intelligence_deterministic_failure_returns_503(
    client, db, test_job, monkeypatch
):
    def _raise(_raw):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        requirement_intelligence_service,
        "extract_deterministic",
        _raise,
    )

    user = _make_user(db)

    response = client.post(
        f"/jobs/{test_job.id}/requirement-intelligence",
        headers=_auth_headers(user),
    )

    assert response.status_code == 503
