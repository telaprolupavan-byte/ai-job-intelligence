from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.main import app
from apps.api.dependencies import get_db
from apps.api.models import (
    Company,
    Job,
    JobMatchResult,
    Preference,
    Profile,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.security import create_access_token
from apps.api.services.job_match_service import (
    JobMatchServiceError,
    calculate_job_match,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_user(db, *, label: str) -> User:
    user = User(
        id=uuid4(),
        email=f"{label}-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )

    db.add(user)
    db.flush()

    profile = Profile(
        id=uuid4(),
        user_id=user.id,
        full_name=f"{label} user",
        years_experience=3.0,
        target_titles=["AI Engineer"],
    )

    preferences = Preference(
        id=uuid4(),
        user_id=user.id,
        employment_types=["full_time"],
        remote_preference="remote",
    )

    db.add(profile)
    db.add(preferences)
    db.flush()

    return user


def make_resume_version(
    db,
    *,
    user: User,
    content_text: str,
    name: str,
    is_master: bool,
) -> ResumeVersion:
    resume = Resume(
        id=uuid4(),
        user_id=user.id,
        filename=f"{name}.txt",
        original_text=content_text,
    )

    db.add(resume)
    db.flush()

    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name=name,
        content_text=content_text,
        content_fingerprint=compute_content_fingerprint(content_text),
        original_filename=f"{name}.txt",
        storage_path=f"/tmp/{name}-{uuid4()}.txt",
        is_master=is_master,
    )

    db.add(version)
    db.flush()

    return version


def make_job(db) -> Job:
    company = Company(
        id=uuid4(),
        name="Test Company",
        normalized_name="test company",
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
        description="Build machine learning applications.",
        requirements="3+ years of experience with Python and Docker.",
        source="test",
        source_url=f"https://example.com/jobs/{uuid4()}",
    )

    db.add(job)
    db.flush()

    return job


def test_explicit_resume_version_id_uses_that_exact_version(db):
    user = make_user(db, label="explicit")
    job = make_job(db)

    make_resume_version(
        db,
        user=user,
        content_text=(
            "SKILLS\nDocker\n\nEXPERIENCE\n- Built Docker deployments."
        ),
        name="Docker-only resume",
        is_master=True,
    )

    python_version = make_resume_version(
        db,
        user=user,
        content_text=(
            "SKILLS\nPython, Docker\n\n"
            "EXPERIENCE\n- Built Python and Docker deployments."
        ),
        name="Python + Docker resume",
        is_master=False,
    )

    match_record = calculate_job_match(
        db=db,
        current_user=user,
        job_id=job.id,
        resume_version_id=python_version.id,
    )

    # The explicit ResumeVersion must be the one actually used/persisted,
    # not the master/most-recent default.
    assert match_record.resume_version_id == python_version.id


def test_default_behavior_remains_compatible_when_no_version_given(db):
    user = make_user(db, label="default")
    job = make_job(db)

    master_version = make_resume_version(
        db,
        user=user,
        content_text=(
            "SKILLS\nPython, Docker\n\n"
            "EXPERIENCE\n- Built Python and Docker deployments."
        ),
        name="Master Resume",
        is_master=True,
    )

    match_record = calculate_job_match(
        db=db,
        current_user=user,
        job_id=job.id,
    )

    # Unchanged default: the master ResumeVersion of the user's most
    # recent Resume is used when no explicit version is requested.
    assert match_record.resume_version_id == master_version.id


def test_cross_user_resume_version_is_rejected(db):
    owner = make_user(db, label="owner")
    attacker = make_user(db, label="attacker")
    job = make_job(db)

    owners_version = make_resume_version(
        db,
        user=owner,
        content_text="SKILLS\nPython\n\nEXPERIENCE\n- Built Python services.",
        name="Owner Resume",
        is_master=True,
    )

    with pytest.raises(JobMatchServiceError) as exc_info:
        calculate_job_match(
            db=db,
            current_user=attacker,
            job_id=job.id,
            resume_version_id=owners_version.id,
        )

    assert exc_info.value.status_code == 404


def test_nonexistent_resume_version_id_is_rejected(db):
    user = make_user(db, label="ghost")
    job = make_job(db)

    with pytest.raises(JobMatchServiceError) as exc_info:
        calculate_job_match(
            db=db,
            current_user=user,
            job_id=job.id,
            resume_version_id=uuid4(),
        )

    assert exc_info.value.status_code == 404


def test_api_rejects_another_users_resume_version_id(client, db):
    owner = make_user(db, label="api-owner")
    attacker = make_user(db, label="api-attacker")
    job = make_job(db)

    owners_version = make_resume_version(
        db,
        user=owner,
        content_text="SKILLS\nPython\n\nEXPERIENCE\n- Built Python services.",
        name="Owner Resume",
        is_master=True,
    )

    # The attacker also has their own resume, so the endpoint would
    # otherwise happily fall back to default selection; we want to prove
    # the explicit (stolen) resume_version_id is rejected outright.
    make_resume_version(
        db,
        user=attacker,
        content_text="SKILLS\nDocker\n\nEXPERIENCE\n- Built Docker services.",
        name="Attacker Resume",
        is_master=True,
    )

    token = create_access_token(str(attacker.id))

    response = client.post(
        f"/jobs/{job.id}/match",
        params={"resume_version_id": str(owners_version.id)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404

    # No match record should have been persisted against the other
    # user's resume version.
    leaked = (
        db.query(JobMatchResult)
        .filter(JobMatchResult.resume_version_id == owners_version.id)
        .first()
    )

    assert leaked is None


def test_api_accepts_explicit_resume_version_id(client, db):
    user = make_user(db, label="api-explicit")
    job = make_job(db)

    make_resume_version(
        db,
        user=user,
        content_text="SKILLS\nDocker\n\nEXPERIENCE\n- Built Docker services.",
        name="Docker-only resume",
        is_master=True,
    )

    python_version = make_resume_version(
        db,
        user=user,
        content_text=(
            "SKILLS\nPython, Docker\n\n"
            "EXPERIENCE\n- Built Python and Docker deployments."
        ),
        name="Python + Docker resume",
        is_master=False,
    )

    token = create_access_token(str(user.id))

    response = client.post(
        f"/jobs/{job.id}/match",
        params={"resume_version_id": str(python_version.id)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["resume_version_id"] == str(python_version.id)


# ---------------------------------------------------------------------------
# JobMatchResult must not pin the records it is derived from.
#
# Its user_id/job_id/resume_version_id foreign keys were the only ones in
# the analysis tables created without ON DELETE CASCADE, so a persisted
# match raised ForeignKeyViolation on any attempt to delete the user, job
# or resume version behind it - blocking account deletion and job
# retirement alike. Every sibling table (ats_alignment_results,
# gap_analyses, job_eligibility_results, requirement_intelligence,
# resume_ai_analyses) already cascaded.
# ---------------------------------------------------------------------------

def _match_row_exists(db, match_id) -> bool:
    """Ask the database, not the session.

    ON DELETE CASCADE runs inside Postgres, so SQLAlchemy's identity map
    still holds the deleted object; `db.get()` would return it from cache
    and the assertion would pass whether or not the constraint cascades.
    """
    return db.execute(
        select(JobMatchResult.id).where(JobMatchResult.id == match_id)
    ).first() is not None


def _persist_match(db, *, user, job, resume_version) -> JobMatchResult:
    record = JobMatchResult(
        id=uuid4(),
        user_id=user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        engine_version="1.0.0",
        score=75.0,
        confidence="medium",
        result={"score": 75.0},
    )
    db.add(record)
    db.flush()
    return record


def test_deleting_a_job_cascades_to_its_job_match_results(db):
    user = make_user(db, label="cascade-job")
    job = make_job(db)
    version = make_resume_version(
        db,
        user=user,
        content_text="Python and Docker experience.",
        name="cascade",
        is_master=True,
    )
    record = _persist_match(db, user=user, job=job, resume_version=version)

    db.delete(job)
    db.flush()

    assert not _match_row_exists(db, record.id)


def test_deleting_a_user_cascades_to_their_job_match_results(db):
    user = make_user(db, label="cascade-user")
    job = make_job(db)
    version = make_resume_version(
        db,
        user=user,
        content_text="Python and Docker experience.",
        name="cascade",
        is_master=True,
    )
    record = _persist_match(db, user=user, job=job, resume_version=version)

    db.delete(user)
    db.flush()

    assert not _match_row_exists(db, record.id)


def test_deleting_a_resume_version_cascades_to_its_job_match_results(db):
    user = make_user(db, label="cascade-version")
    job = make_job(db)
    version = make_resume_version(
        db,
        user=user,
        content_text="Python and Docker experience.",
        name="cascade",
        is_master=True,
    )
    record = _persist_match(db, user=user, job=job, resume_version=version)

    db.delete(version)
    db.flush()

    assert not _match_row_exists(db, record.id)
