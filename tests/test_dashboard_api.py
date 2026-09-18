"""Authenticated API tests for GET /dashboard.

The dashboard endpoint aggregates read-only summaries from other modules
(Resume, ATS Alignment, Job discovery). It must never fabricate a value for
a module that has no real data yet — see docs on the Dashboard's data
rules — so these tests pin both the "real data present" and the "truthful
empty state" shapes.
"""

from datetime import datetime, timedelta, timezone
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


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"dashboard-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id, years_experience=5.0))
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


def _make_job(
    db,
    *,
    is_active: bool = True,
    first_seen_at: datetime | None = None,
    employment_type: str | None = "full_time",
) -> Job:
    company = Company(
        id=uuid4(),
        name=f"Dashboard API Test Co {uuid4()}",
        normalized_name="dashboard api test co",
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
        employment_type=employment_type,
        description="5+ years of Python development required.",
        source="test",
        source_url=f"https://example.com/job/{uuid4()}",
        is_active=is_active,
    )
    if first_seen_at is not None:
        job.first_seen_at = first_seen_at

    db.add(job)
    db.flush()

    return job


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_dashboard_requires_authentication(client):
    response = client.get("/dashboard")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Truthful empty states for a brand-new user
# ---------------------------------------------------------------------------


def test_dashboard_defaults_for_new_user(client, db):
    user = _make_user(db)

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    data = response.json()

    assert data["resume"] == {"status": "not_ready", "name": None}
    assert data["ats"] == {"score": None, "checked_at": None}
    assert data["jobs"] == {"today_count": 0, "today_employment_types": []}
    assert data["applications"] == {"available": False}


# ---------------------------------------------------------------------------
# Resume readiness reflects real Resume data
# ---------------------------------------------------------------------------


def test_dashboard_reflects_uploaded_resume(client, db):
    user = _make_user(db)
    db.add(Resume(id=uuid4(), user_id=user.id, filename="my-resume.pdf"))
    db.flush()

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    data = response.json()
    assert data["resume"] == {"status": "ready", "name": "my-resume.pdf"}


# ---------------------------------------------------------------------------
# ATS score reflects the real, latest AtsAlignmentResult
# ---------------------------------------------------------------------------


def test_dashboard_reflects_latest_ats_alignment_score(client, db):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="Python developer.")
    job = _make_job(db)

    ats_response = client.post(
        f"/jobs/{job.id}/ats", headers=_auth_headers(user)
    )
    assert ats_response.status_code == 200

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    data = response.json()
    assert data["ats"]["score"] == ats_response.json()["overall_score"]
    assert data["ats"]["checked_at"] is not None


def test_dashboard_never_leaks_another_users_ats_score(client, db):
    user_a = _make_user(db)
    user_b = _make_user(db)

    _make_resume_version(db, user=user_a, content_text="Python developer.")
    job = _make_job(db)

    client.post(f"/jobs/{job.id}/ats", headers=_auth_headers(user_a))

    response = client.get("/dashboard", headers=_auth_headers(user_b))

    assert response.status_code == 200
    assert response.json()["ats"] == {"score": None, "checked_at": None}


# ---------------------------------------------------------------------------
# Today's Jobs reflects real, active Job rows discovered today
# ---------------------------------------------------------------------------


def test_dashboard_jobs_today_count_counts_only_active_jobs_seen_today(
    client, db
):
    user = _make_user(db)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _make_job(db, is_active=True, first_seen_at=now, employment_type="full_time")
    _make_job(
        db,
        is_active=True,
        first_seen_at=now - timedelta(days=3),
        employment_type="contract",
    )
    _make_job(db, is_active=False, first_seen_at=now, employment_type="contract")

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    assert response.json()["jobs"] == {
        "today_count": 1,
        "today_employment_types": ["full_time"],
    }


def test_dashboard_jobs_today_employment_types_empty_when_no_jobs_today(
    client, db
):
    user = _make_user(db)

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    assert response.json()["jobs"] == {
        "today_count": 0,
        "today_employment_types": [],
    }


def test_dashboard_jobs_today_employment_types_ignores_null_type(client, db):
    user = _make_user(db)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _make_job(db, is_active=True, first_seen_at=now, employment_type=None)

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    data = response.json()
    assert data["jobs"]["today_count"] == 1
    assert data["jobs"]["today_employment_types"] == []
