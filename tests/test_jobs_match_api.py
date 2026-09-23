from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.models import (
    Company,
    Job,
    Preference,
    Profile,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.security import create_access_token
from apps.api.dependencies import get_db
from apps.api.models import JobMatchResult
from apps.api.services.resume_fingerprint import compute_content_fingerprint


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    user = User(
        id=uuid4(),
        email=f"match-test-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )

    db.add(user)
    db.flush()

    profile = Profile(
        id=uuid4(),
        user_id=user.id,
        full_name="Match Test User",
        location="Newark, NJ",
        years_experience=3.0,
        target_titles=["AI Engineer", "Machine Learning Engineer"],
    )

    preferences = Preference(
        id=uuid4(),
        user_id=user.id,
        employment_types=["full_time"],
        locations=["Newark"],
        remote_preference="remote",
    )

    db.add(profile)
    db.add(preferences)
    db.flush()

    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture
def test_job(db):
    company = Company(
        id=uuid4(),
        name="Test AI Company",
        normalized_name="test ai company",
    )

    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="AI Engineer",
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description=(
            "Build machine learning and generative AI applications."
        ),
        requirements=(
            "3+ years of experience with Python, machine learning, "
            "and Docker."
        ),
        responsibilities=(
            "Develop AI applications and deploy machine learning models."
        ),
        source="test",
        source_url="https://example.com/jobs/test-ai-engineer",
        application_url="https://example.com/apply/test-ai-engineer",
    )

    db.add(job)
    db.flush()

    return job


@pytest.fixture
def test_resume(db, test_user):
    resume = Resume(
        id=uuid4(),
        user_id=test_user.id,
        filename="test-resume.txt",
        original_text=(
            "AI Engineer with 3 years of experience. "
            "Python, machine learning, Docker, AWS."
        ),
    )

    db.add(resume)
    db.flush()

    content_text = (
        "PROFESSIONAL SUMMARY\n"
        "AI Engineer with 3 years of experience building "
        "machine learning applications.\n\n"
        "EXPERIENCE\n"
        "- Developed machine learning applications using Python.\n"
        "- Built Docker-based deployments for AI services.\n\n"
        "SKILLS\n"
        "Python, Machine Learning, Docker, AWS\n\n"
        "PROJECTS\n"
        "- Built a generative AI application using Python."
    )

    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name="Master Resume",
        content_text=content_text,
        content_fingerprint=compute_content_fingerprint(content_text),
        original_filename="test-resume.txt",
        storage_path="/tmp/test-resume-fixture.txt",
        is_master=True,
    )

    db.add(version)
    db.flush()

    return resume
def test_calculate_job_match_success(
    client,
    db,
    test_user,
    test_job,
    test_resume,
    auth_headers,
):
    response = client.post(
        f"/jobs/{test_job.id}/match",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == str(test_job.id)
    assert data["resume_version_id"]
    assert data["id"]

    assert 0 <= data["score"] <= 100
    assert data["confidence"] in {
        "high",
        "medium",
        "low",
    }

    assert isinstance(data["strengths"], list)
    assert isinstance(data["skill_gaps"], list)
    assert isinstance(data["components"], list)

    component_names = {
        component["name"]
        for component in data["components"]
    }

    assert "must_have_requirements" in component_names
    assert "preferred_requirements" in component_names
    assert "experience" in component_names
    assert "role_alignment" in component_names
    assert "location" in component_names
    assert "employment_type" in component_names


def test_calculate_job_match_persists_result(
    client,
    db,
    test_user,
    test_job,
    test_resume,
    auth_headers,
):
    response = client.post(
        f"/jobs/{test_job.id}/match",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    match = (
        db.query(JobMatchResult)
        .filter(JobMatchResult.id == data["id"])
        .first()
    )

    assert match is not None
    assert match.user_id == test_user.id
    assert match.job_id == test_job.id
    assert match.resume_version_id == test_resume.versions[0].id
    assert match.engine_version == "1.0.0"
    assert 0 <= match.score <= 100
    assert match.confidence in {
        "high",
        "medium",
        "low",
    }
    assert isinstance(match.result, dict)


def test_calculate_job_match_job_not_found(
    client,
    auth_headers,
):
    missing_job_id = uuid4()

    response = client.post(
        f"/jobs/{missing_job_id}/match",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_calculate_job_match_without_resume(
    client,
    db,
    test_user,
    test_job,
    auth_headers,
):
    response = client.post(
        f"/jobs/{test_job.id}/match",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No resume found for this user"
    )


def test_calculate_job_match_without_authentication(
    client,
    test_job,
):
    response = client.post(
        f"/jobs/{test_job.id}/match",
    )

    assert response.status_code == 401


def test_calculate_job_match_rejects_other_users_resume_version_id(
    client,
    db,
    test_job,
    test_resume,
    auth_headers,
):
    """A resume_version_id belonging to a different user must be
    rejected the same way as a nonexistent one, never exposing that
    user's resume data or even confirming the ID exists."""
    other_user = User(
        id=uuid4(),
        email=f"match-other-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(other_user)
    db.flush()

    other_token = create_access_token(str(other_user.id))

    response = client.post(
        f"/jobs/{test_job.id}/match",
        params={
            "resume_version_id": str(test_resume.versions[0].id),
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume version not found."

# ---------------------------------------------------------------------------
# AJI-023 — GET /jobs/{job_id}/match (read-only latest result)
# ---------------------------------------------------------------------------


def _make_version(db, resume, *, name: str, is_master: bool) -> ResumeVersion:
    content_text = f"{name}\nSKILLS\nPython, Machine Learning, Docker"
    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name=name,
        content_text=content_text,
        content_fingerprint=compute_content_fingerprint(content_text),
        original_filename="test-resume.txt",
        storage_path=f"/tmp/{uuid4()}.txt",
        is_master=is_master,
    )
    db.add(version)
    db.flush()
    return version


def test_get_job_match_404s_before_any_calculation(
    client, db, test_job, test_resume, auth_headers
):
    response = client.get(f"/jobs/{test_job.id}/match", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Job Match has not been calculated for this job yet."
    )
    # A read never calculates anything.
    assert (
        db.query(JobMatchResult)
        .filter(JobMatchResult.job_id == test_job.id)
        .count()
        == 0
    )


def test_get_job_match_returns_the_calculated_result_unchanged(
    client, test_job, test_resume, auth_headers
):
    created = client.post(f"/jobs/{test_job.id}/match", headers=auth_headers)
    assert created.status_code == 200

    response = client.get(f"/jobs/{test_job.id}/match", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == created.json()


def test_get_job_match_is_pinned_to_the_requested_resume_version(
    client, db, test_job, test_resume, auth_headers
):
    master = test_resume.versions[0]
    tailored = _make_version(db, test_resume, name="Tailored", is_master=False)

    client.post(
        f"/jobs/{test_job.id}/match",
        params={"resume_version_id": str(master.id)},
        headers=auth_headers,
    )

    pinned_master = client.get(
        f"/jobs/{test_job.id}/match",
        params={"resume_version_id": str(master.id)},
        headers=auth_headers,
    )
    assert pinned_master.status_code == 200
    assert pinned_master.json()["resume_version_id"] == str(master.id)

    # Nothing has been calculated for the tailored version yet.
    pinned_tailored = client.get(
        f"/jobs/{test_job.id}/match",
        params={"resume_version_id": str(tailored.id)},
        headers=auth_headers,
    )
    assert pinned_tailored.status_code == 404


def test_get_job_match_never_returns_another_users_result(
    client, db, test_job, test_resume, auth_headers
):
    created = client.post(f"/jobs/{test_job.id}/match", headers=auth_headers)
    assert created.status_code == 200

    other_user = User(
        id=uuid4(),
        email=f"match-read-other-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(other_user)
    db.flush()
    other_headers = {
        "Authorization": f"Bearer {create_access_token(str(other_user.id))}"
    }

    response = client.get(f"/jobs/{test_job.id}/match", headers=other_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Job Match has not been calculated for this job yet."
    )

    # Pinning to the owner's resume version still reveals nothing.
    pinned = client.get(
        f"/jobs/{test_job.id}/match",
        params={"resume_version_id": created.json()["resume_version_id"]},
        headers=other_headers,
    )
    assert pinned.status_code == 404


def test_get_job_match_rejects_malformed_resume_version_id(
    client, test_job, auth_headers
):
    response = client.get(
        f"/jobs/{test_job.id}/match",
        params={"resume_version_id": "not-a-uuid"},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume version not found."


def test_get_job_match_requires_authentication(client, test_job):
    assert client.get(f"/jobs/{test_job.id}/match").status_code == 401


def test_get_job_match_unknown_job(client, auth_headers):
    response = client.get(f"/jobs/{uuid4()}/match", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
