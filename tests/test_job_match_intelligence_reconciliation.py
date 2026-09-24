"""DB-backed tests for Job Match's AJI-014 reconciliation with AJI-012
Job Intelligence: job-side requirements are sourced from a persisted/
generated `JobIntelligence` snapshot instead of Job Match re-parsing raw
JD text itself, and `calculate_job_match()` becomes idempotent/keyed
exactly like `calculate_ats_alignment()`.
"""

from uuid import uuid4

import pytest

from apps.api.models import (
    Company,
    Job,
    JobIntelligence,
    JobMatchResult,
    Preference,
    Profile,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services import job_match_service
from apps.api.services.job_match_service import (
    JobMatchServiceError,
    calculate_job_match,
)
from apps.api.services.job_intelligence import service as job_intelligence_service
from apps.api.services.resume_fingerprint import compute_content_fingerprint

from tests.support.job_intelligence import make_job_intelligence, skill_item


def make_user(db, *, label: str, years_experience: float | None = 5.0) -> User:
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
        years_experience=years_experience,
    )
    preferences = Preference(id=uuid4(), user_id=user.id)

    db.add(profile)
    db.add(preferences)
    db.flush()
    db.refresh(user)

    return user


def make_resume_version(
    db,
    *,
    user: User,
    content_text: str,
    name: str = "resume",
    is_master: bool = True,
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


def make_job(db, *, responsibilities: str | None = None) -> Job:
    company = Company(
        id=uuid4(),
        name="Match Reconciliation Co",
        normalized_name="match reconciliation co",
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
        requirements="5+ years of Python experience required.",
        responsibilities=responsibilities,
        source="test",
        source_url=f"https://example.com/jobs/{uuid4()}",
    )
    db.add(job)
    db.flush()

    return job


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        return {}


@pytest.fixture(autouse=True)
def fake_ai_provider(monkeypatch):
    monkeypatch.setattr(
        job_intelligence_service,
        "create_job_intelligence_provider",
        lambda: FakeProvider(),
    )


# ---------------------------------------------------------------------------
# Reuses AJI-012 Job Intelligence instead of re-parsing raw JD text
# ---------------------------------------------------------------------------


def test_uses_existing_job_intelligence_snapshot_requirements(db):
    """
    A skill present in a persisted JobIntelligence snapshot but absent
    from the job's own raw description/requirements text must still
    drive the must-have requirement set — proving Job Match reads
    requirements from JobIntelligence, not by re-parsing Job text itself.
    """
    user = make_user(db, label="reuse")
    job = make_job(db)
    make_job_intelligence(
        db,
        job=job,
        required_skills=[skill_item("kubernetes")],
    )
    make_resume_version(
        db, user=user, content_text="SKILLS\nKubernetes\n\nEXPERIENCE\n- Ran Kubernetes clusters."
    )

    match = calculate_job_match(db=db, current_user=user, job_id=job.id)

    must_have_component = next(
        component
        for component in match.result["components"]
        if component["name"] == "must_have_requirements"
    )

    assert must_have_component["score"] == must_have_component["max_score"]
    matched_skills = {item["skill"] for item in match.result["must_have_matches"]}
    assert "kubernetes" in matched_skills


def test_generates_job_intelligence_when_missing(db):
    user = make_user(db, label="autogen")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer. Skills: Python.")

    match = calculate_job_match(db=db, current_user=user, job_id=job.id)

    assert match.job_intelligence_id is not None

    snapshot = (
        db.query(JobIntelligence)
        .filter(JobIntelligence.job_id == job.id)
        .first()
    )
    assert snapshot is not None
    assert match.job_intelligence_id == snapshot.id


def test_responsibilities_are_not_treated_as_requirements(db):
    """
    AJI-012 deliberately excludes `Job.responsibilities` from the
    requirement text it classifies (a responsibility is never a hard
    requirement). Job Match, now sourced from AJI-012, must inherit that
    exclusion instead of the previous behavior of feeding
    responsibilities text into its own requirement extraction.
    """
    user = make_user(db, label="responsibilities")
    job = make_job(
        db,
        responsibilities="Own our Go microservices in production.",
    )
    make_resume_version(db, user=user, content_text="Python developer.")

    match = calculate_job_match(db=db, current_user=user, job_id=job.id)

    all_skills = {
        item["skill"]
        for item in (
            match.result["must_have_matches"]
            + match.result["must_have_gaps"]
            + match.result["preferred_matches"]
            + match.result["preferred_gaps"]
        )
    }

    assert "go" not in all_skills


# ---------------------------------------------------------------------------
# Idempotency / versioning
# ---------------------------------------------------------------------------


def test_same_inputs_reuse_existing_match(db):
    user = make_user(db, label="idempotent")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])
    make_resume_version(db, user=user, content_text="Python developer. Skills: Python.")

    first = calculate_job_match(db=db, current_user=user, job_id=job.id)
    second = calculate_job_match(db=db, current_user=user, job_id=job.id)

    assert first.id == second.id

    count = (
        db.query(JobMatchResult)
        .filter(JobMatchResult.user_id == user.id, JobMatchResult.job_id == job.id)
        .count()
    )
    assert count == 1


def test_changed_resume_version_creates_new_match(db):
    user = make_user(db, label="resume-change")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    v1 = make_resume_version(
        db, user=user, content_text="Python developer.", name="v1", is_master=True
    )
    first = calculate_job_match(db=db, current_user=user, job_id=job.id)
    assert first.resume_version_id == v1.id

    v2 = make_resume_version(
        db,
        user=user,
        content_text="Python and Kubernetes engineer.",
        name="v2",
        is_master=True,
    )
    second = calculate_job_match(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.resume_version_id == v2.id


def test_changed_job_intelligence_snapshot_creates_new_match(db):
    user = make_user(db, label="ji-change")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer.")

    make_job_intelligence(
        db,
        job=job,
        required_skills=[skill_item("python")],
        content_fingerprint="fp-1",
    )
    first = calculate_job_match(db=db, current_user=user, job_id=job.id)

    make_job_intelligence(
        db,
        job=job,
        required_skills=[skill_item("python"), skill_item("go")],
        content_fingerprint="fp-2",
    )
    second = calculate_job_match(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.job_intelligence_id != first.job_intelligence_id


def test_bumped_engine_version_creates_new_match(db, monkeypatch):
    user = make_user(db, label="engine-version")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])
    make_resume_version(db, user=user, content_text="Python developer.")

    first = calculate_job_match(db=db, current_user=user, job_id=job.id)

    monkeypatch.setattr(job_match_service, "ENGINE_VERSION", "9.9.9")
    monkeypatch.setattr("services.job_matching.scorer.ENGINE_VERSION", "9.9.9")

    second = calculate_job_match(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.engine_version == "9.9.9"


# ---------------------------------------------------------------------------
# Job Intelligence unavailable
# ---------------------------------------------------------------------------


def test_job_intelligence_generation_failure_surfaces_as_service_error(
    db, monkeypatch
):
    def _raise_deterministic_failure(raw):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        job_intelligence_service, "extract_deterministic", _raise_deterministic_failure
    )

    user = make_user(db, label="ji-failure")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer.")

    with pytest.raises(JobMatchServiceError) as exc_info:
        calculate_job_match(db=db, current_user=user, job_id=job.id)

    assert exc_info.value.status_code == 503
