"""Authenticated API tests for the Dashboard aggregate read (UI-DASH-001):
GET /dashboard.

Every field is expected to come from a real, already-existing artifact
(Resume, ResumeAIAnalysis, AtsAlignmentResult, Job) — these tests assert
that an empty account gets honest pending/empty values (never fabricated
data), and that real rows are surfaced once they exist.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import (
    AtsAlignmentResult,
    Company,
    Job,
    JobIntelligence,
    Resume,
    ResumeAIAnalysis,
    ResumeVersion,
    User,
)
from apps.api.security import create_access_token
from apps.api.services.resume_fingerprint import compute_content_fingerprint


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"dashboard-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
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


def _make_job(db, *, employment_type: str | None, first_seen_at: datetime) -> Job:
    company = Company(
        id=uuid4(),
        name="Dashboard Test Co",
        normalized_name="dashboard test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Software Engineer",
        employment_type=employment_type,
        source="test",
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
        is_active=True,
    )
    db.add(job)
    db.flush()

    return job


def _make_ats_alignment_result(
    db, *, user: User, job: Job, resume_version: ResumeVersion, overall_score: float
) -> AtsAlignmentResult:
    job_intelligence = JobIntelligence(
        id=uuid4(),
        job_id=job.id,
        content_fingerprint="fingerprint",
        raw_jd_snapshot={},
        source="test",
        analysis_version="1",
        analyzer_version="1",
        prompt_version="1",
        structured_intelligence={},
    )
    db.add(job_intelligence)
    db.flush()

    result = AtsAlignmentResult(
        id=uuid4(),
        user_id=user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        job_intelligence_id=job_intelligence.id,
        job_content_fingerprint="fingerprint",
        engine_version="1",
        overall_score=overall_score,
        confidence="high",
        result={},
    )
    db.add(result)
    db.flush()

    return result


def test_dashboard_empty_account_returns_pending_states(client, db):
    user = _make_user(db)
    db.commit()

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    data = response.json()

    assert data["resume"] == {"status": "not_ready", "name": None}
    assert data["validation"] == {"status": "pending"}
    assert data["ats"] == {"score": None, "status": "not_checked"}
    assert data["last_checked_at"] is None
    assert data["applications"] == {"available": False, "active_count": 0}
    assert data["jobs"]["available"] is True
    assert data["jobs"]["recent"] == []


def test_dashboard_reflects_uploaded_but_unanalyzed_resume(client, db):
    user = _make_user(db)
    _make_resume_version(db, user=user, content_text="my resume text")
    db.commit()

    response = client.get("/dashboard", headers=_auth_headers(user))
    data = response.json()

    assert data["resume"]["status"] == "ready"
    assert data["resume"]["name"] == "resume.txt"
    # No ResumeAIAnalysis or AtsAlignmentResult exists yet: still pending,
    # never fabricated.
    assert data["validation"] == {"status": "pending"}
    assert data["ats"] == {"score": None, "status": "not_checked"}
    assert data["last_checked_at"] is None


def test_dashboard_reflects_real_resume_analysis(client, db):
    user = _make_user(db)
    version = _make_resume_version(db, user=user, content_text="my resume text")

    analysis = ResumeAIAnalysis(
        id=uuid4(),
        user_id=user.id,
        resume_version_id=version.id,
        analysis_version="1",
        analyzer_version="1",
        prompt_version="1",
        analysis_result={},
    )
    db.add(analysis)
    db.commit()

    response = client.get("/dashboard", headers=_auth_headers(user))
    data = response.json()

    assert data["validation"] == {"status": "analyzed"}
    assert data["last_checked_at"] is not None


def test_dashboard_reflects_real_ats_alignment_score(client, db):
    user = _make_user(db)
    version = _make_resume_version(db, user=user, content_text="my resume text")
    job = _make_job(
        db, employment_type="full_time", first_seen_at=datetime.utcnow()
    )

    _make_ats_alignment_result(
        db, user=user, job=job, resume_version=version, overall_score=87.0
    )
    db.commit()

    response = client.get("/dashboard", headers=_auth_headers(user))
    data = response.json()

    assert data["ats"] == {"score": 87, "status": "pass"}
    assert data["last_checked_at"] is not None


def test_dashboard_ats_below_threshold_is_needs_improvement(client, db):
    user = _make_user(db)
    version = _make_resume_version(db, user=user, content_text="my resume text")
    job = _make_job(
        db, employment_type="full_time", first_seen_at=datetime.utcnow()
    )

    _make_ats_alignment_result(
        db, user=user, job=job, resume_version=version, overall_score=42.0
    )
    db.commit()

    response = client.get("/dashboard", headers=_auth_headers(user))
    data = response.json()

    assert data["ats"] == {"score": 42, "status": "needs_improvement"}


def test_dashboard_job_counts_and_recent_list_are_real(client, db):
    user = _make_user(db)
    now = datetime.utcnow()

    _make_job(db, employment_type="full_time", first_seen_at=now)
    _make_job(db, employment_type="contract", first_seen_at=now)
    # Discovered a week ago: counted in the recent list and the
    # employment-type totals, but never in "today's" count.
    _make_job(
        db, employment_type="full_time", first_seen_at=now - timedelta(days=7)
    )
    db.commit()

    response = client.get("/dashboard", headers=_auth_headers(user))
    data = response.json()

    assert data["jobs"]["today_count"] == 2
    assert data["jobs"]["full_time_count"] == 2
    assert data["jobs"]["contract_count"] == 1
    assert len(data["jobs"]["recent"]) == 3


def test_dashboard_combines_naive_and_aware_timestamps(client, db):
    """ResumeAIAnalysis.created_at is a naive DateTime column while
    AtsAlignmentResult.created_at is timezone-aware — regression guard
    for comparing them together when picking the most recent one."""
    user = _make_user(db)
    version = _make_resume_version(db, user=user, content_text="my resume text")
    job = _make_job(
        db, employment_type="full_time", first_seen_at=datetime.utcnow()
    )

    analysis = ResumeAIAnalysis(
        id=uuid4(),
        user_id=user.id,
        resume_version_id=version.id,
        analysis_version="1",
        analyzer_version="1",
        prompt_version="1",
        analysis_result={},
    )
    db.add(analysis)

    _make_ats_alignment_result(
        db, user=user, job=job, resume_version=version, overall_score=87.0
    )
    db.commit()

    response = client.get("/dashboard", headers=_auth_headers(user))

    assert response.status_code == 200
    data = response.json()

    assert data["validation"] == {"status": "analyzed"}
    assert data["ats"]["score"] == 87
    assert data["last_checked_at"] is not None


def test_dashboard_requires_authentication(client):
    response = client.get("/dashboard")

    assert response.status_code in (401, 403)
