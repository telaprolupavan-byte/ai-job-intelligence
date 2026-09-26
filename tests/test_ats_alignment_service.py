"""DB-backed tests for the ATS Alignment orchestration service (AJI-013,
integrated with Requirement Intelligence by AJI-020C).

Requirement content is seeded directly as a `RequirementIntelligence`
row (via `make_requirement_intelligence`/`ri_skill_item`/
`ri_experience_item` below) rather than via `JobIntelligence` — since
AJI-020C, `RequirementIntelligence` is the actual source ATS Alignment
scores against (see apps/api/services/ats_alignment_service.py's module
docstring). `make_job_intelligence` is kept only for the one test that
exercises the still-populated `job_intelligence_id` lineage column.
"""

from uuid import uuid4

import pytest

from apps.api.models import (
    Company,
    Job,
    JobIntelligence,
    Preference,
    Profile,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services import ats_alignment_service
from apps.api.services.ats_alignment_service import (
    ATSAlignmentServiceError,
    calculate_ats_alignment,
    get_latest_ats_alignment,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint

from tests.support.requirement_intelligence import (
    make_requirement_intelligence,
    ri_skill_item,
)


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


def make_job(db) -> Job:
    company = Company(
        id=uuid4(),
        name="ATS Test Co",
        normalized_name="ats test co",
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
        source="test",
        source_url=f"https://example.com/jobs/{uuid4()}",
    )
    db.add(job)
    db.flush()

    return job


def make_job_intelligence(
    db,
    *,
    job: Job,
    required_skills: list[dict] | None = None,
    preferred_skills: list[dict] | None = None,
    required_experience: list[dict] | None = None,
    education: list[dict] | None = None,
    certifications: list[dict] | None = None,
    content_fingerprint: str | None = None,
) -> JobIntelligence:
    structured = {
        "analysis_version": "1.0",
        "job_id": str(job.id),
        "identity": {"original_title": job.title},
        "employment": {"employment_type": "full_time"},
        "location": {"remote_type": "remote"},
        "required_skills": required_skills or [],
        "preferred_skills": preferred_skills or [],
        "required_experience": required_experience or [],
        "preferred_experience": [],
        "education": education or [],
        "certifications": certifications or [],
        "responsibilities": [],
        "authorization": {},
        "compensation": {},
        "domain": {},
    }

    record = JobIntelligence(
        id=uuid4(),
        job_id=job.id,
        content_fingerprint=content_fingerprint or f"fingerprint-{uuid4()}",
        raw_jd_snapshot={"title": job.title},
        source="test",
        source_url=job.source_url,
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        extraction_status="complete",
        structured_intelligence=structured,
    )
    db.add(record)
    db.flush()

    return record


def skill_item(canonical_skill: str, *, level: str = "required") -> dict:
    return {
        "canonical_skill": canonical_skill,
        "level": level,
        "evidence_text": f"{canonical_skill} required.",
        "confidence": "high",
    }


def experience_item(minimum_years: float, *, level: str = "required") -> dict:
    return {
        "level": level,
        "minimum_years": minimum_years,
        "evidence_text": f"{minimum_years}+ years required.",
        "confidence": "high",
    }


# ---------------------------------------------------------------------------
# Requirement Intelligence (AJI-020A/B/C) fixture helpers
# ---------------------------------------------------------------------------

def ri_experience_item(
    minimum_years: float,
    *,
    area: str | None = None,
    importance: str = "required",
    item_id: str | None = None,
) -> dict:
    return {
        "id": item_id or f"req-experience-{area or 'general'}",
        "requirement_type": "experience",
        "importance": importance,
        "statement": f"{minimum_years}+ years" + (f" of {area}" if area else ""),
        "canonical_terms": [area] if area else [],
        "raw_text": f"{minimum_years}+ years of experience required.",
        "confidence": "high",
        "experience": {
            "operator": "at_least",
            "minimum_years": minimum_years,
            "area": area,
        },
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_calculate_ats_alignment_happy_path(db):
    user = make_user(db, label="happy", years_experience=6)
    job = make_job(db)
    resume_version = make_resume_version(
        db, user=user, content_text="Experienced Python developer. Skills: Python."
    )
    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[
            ri_skill_item("python"),
            ri_experience_item(5, area="python"),
        ],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert record.user_id == user.id
    assert record.job_id == job.id
    assert record.resume_version_id == resume_version.id
    # AJI-020: Requirement Coverage/Keyword Alignment/Evidence & Experience
    # are all 100 (the one skill and one experience requirement both
    # match), but this resume has no detectable section headings, contact
    # info, or bullet points, so Structure & Parseability scores 20/100
    # (only the "no heading inconsistency" check passes) -> weighted sum
    # 40 + 25 + 25 + (0.1 * 20) = 92, under the must-have ceiling (100).
    assert record.overall_score == 92.0
    assert record.confidence == "high"
    assert len(record.result["requirement_results"]) == 2
    assert len(record.result["score_components"]) == 4


def test_calculate_ats_alignment_generates_job_intelligence_when_missing(
    db, monkeypatch
):
    class FakeProvider:
        provider_name = "fake"
        model_name = "fake-model"

        def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
            return {}

    monkeypatch.setattr(
        "apps.api.services.job_intelligence.service.create_job_intelligence_provider",
        lambda: FakeProvider(),
    )

    user = make_user(db, label="autogen")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer.")

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert record.overall_score is not None
    assert record.job_intelligence_id is not None


# ---------------------------------------------------------------------------
# Idempotency / versioning
# ---------------------------------------------------------------------------

def test_same_inputs_reuse_existing_analysis(db):
    user = make_user(db, label="idempotent")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer. Skills: Python.")
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    first = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)
    second = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert first.id == second.id


def test_changed_resume_version_creates_new_analysis(db):
    user = make_user(db, label="resume-change")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    v1 = make_resume_version(
        db, user=user, content_text="Python developer.", name="v1", is_master=True
    )
    first = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)
    assert first.resume_version_id == v1.id

    v2 = make_resume_version(
        db,
        user=user,
        content_text="Python and Kubernetes engineer.",
        name="v2",
        is_master=True,
    )
    second = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.resume_version_id == v2.id


def test_rechecking_with_new_resume_version_preserves_old_analysis(db):
    """AJI-020: rechecking a job with a new resume version must create a
    new analysis rather than overwrite the old one — both rows must
    remain independently readable by their own resume_version_id."""
    user = make_user(db, label="preserve-history")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    v1 = make_resume_version(
        db, user=user, content_text="Python developer.", name="v1", is_master=True
    )
    first = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)
    first_score = first.overall_score

    make_resume_version(
        db,
        user=user,
        content_text="Go and Rust engineer with no Python experience.",
        name="v2",
        is_master=True,
    )
    calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    # The v1 analysis is untouched: re-reading it by its own resume
    # version id still returns the original score and requirement
    # results, not the v2 recomputation.
    preserved = get_latest_ats_alignment(
        db, user_id=user.id, job_id=job.id, resume_version_id=v1.id
    )

    assert preserved.id == first.id
    assert preserved.overall_score == first_score


def test_two_resume_versions_for_same_job_have_independent_history(db):
    user = make_user(db, label="resume-isolation")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    v1 = make_resume_version(
        db, user=user, content_text="Python developer.", name="v1", is_master=False
    )
    v2 = make_resume_version(
        db, user=user, content_text="Go engineer.", name="v2", is_master=False
    )

    result_v1 = calculate_ats_alignment(
        db=db, current_user=user, job_id=job.id, resume_version_id=v1.id
    )
    result_v2 = calculate_ats_alignment(
        db=db, current_user=user, job_id=job.id, resume_version_id=v2.id
    )

    assert result_v1.id != result_v2.id
    assert result_v1.overall_score != result_v2.overall_score

    fetched_v1 = get_latest_ats_alignment(
        db, user_id=user.id, job_id=job.id, resume_version_id=v1.id
    )
    fetched_v2 = get_latest_ats_alignment(
        db, user_id=user.id, job_id=job.id, resume_version_id=v2.id
    )

    assert fetched_v1.id == result_v1.id
    assert fetched_v2.id == result_v2.id


def test_same_resume_against_two_jobs_is_isolated_per_job(db):
    user = make_user(db, label="job-isolation")
    job_a = make_job(db)
    job_b = make_job(db)
    make_job_intelligence(db, job=job_a, required_skills=[skill_item("python")])
    make_job_intelligence(db, job=job_b, required_skills=[skill_item("go")])
    make_resume_version(db, user=user, content_text="Python developer.")

    result_a = calculate_ats_alignment(db=db, current_user=user, job_id=job_a.id)
    result_b = calculate_ats_alignment(db=db, current_user=user, job_id=job_b.id)

    assert result_a.id != result_b.id
    assert result_a.job_id == job_a.id
    assert result_b.job_id == job_b.id

    assert get_latest_ats_alignment(db, user_id=user.id, job_id=job_a.id).id == (
        result_a.id
    )
    assert get_latest_ats_alignment(db, user_id=user.id, job_id=job_b.id).id == (
        result_b.id
    )


def test_changed_job_intelligence_snapshot_creates_new_analysis(db):
    """`job_intelligence_id` is retained unchanged as a lineage-only
    isolation dimension by AJI-020C (its *content* no longer drives
    scoring — see `test_changed_requirement_intelligence_snapshot_
    creates_new_analysis_and_new_score` below for the dimension that
    now does) — this proves that isolation dimension itself still
    functions exactly as before."""
    user = make_user(db, label="ji-change")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer.")

    make_job_intelligence(
        db, job=job, required_skills=[skill_item("python")],
        content_fingerprint="fp-1",
    )
    first = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    make_job_intelligence(
        db, job=job, required_skills=[skill_item("python"), skill_item("go")],
        content_fingerprint="fp-2",
    )
    second = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.job_intelligence_id != first.job_intelligence_id


def test_changed_requirement_intelligence_snapshot_creates_new_analysis_and_new_score(
    db,
):
    """The AJI-020C dimension that actually drives scoring: a new
    Requirement Intelligence snapshot for the same job produces a new
    ATS row, and (unlike the JobIntelligence-only case above) the
    scored content genuinely changes."""
    user = make_user(db, label="ri-change")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer. Skills: Python.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python")],
        content_fingerprint="ri-fp-1",
    )
    first = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)
    assert first.overall_score > 0.0

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python"), ri_skill_item("kubernetes")],
        content_fingerprint="ri-fp-2",
    )
    second = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.requirement_intelligence_id != first.requirement_intelligence_id
    # kubernetes is missing from the resume, so the score genuinely drops.
    assert second.overall_score < first.overall_score


def test_bumped_engine_version_creates_new_analysis(db, monkeypatch):
    user = make_user(db, label="engine-version")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer.")
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    first = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    # Both bindings are patched: the orchestration layer's own
    # `ENGINE_VERSION` name (used for the idempotency cache filter) and
    # the pure engine's `ENGINE_VERSION` (what a fresh
    # `evaluate_ats_alignment()` call actually stamps onto its result).
    # In production these always move together (both come from the same
    # `services.ats_alignment.engine.ENGINE_VERSION` constant, re-read on
    # process start) — this test patches both to simulate that.
    monkeypatch.setattr(ats_alignment_service, "ENGINE_VERSION", "9.9.9")
    monkeypatch.setattr("services.ats_alignment.engine.ENGINE_VERSION", "9.9.9")
    second = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.engine_version == "9.9.9"


# ---------------------------------------------------------------------------
# Resume version selection
# ---------------------------------------------------------------------------

def test_explicit_resume_version_id_is_used(db):
    user = make_user(db, label="explicit")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    older = make_resume_version(
        db, user=user, content_text="Python.", name="older", is_master=False
    )
    make_resume_version(
        db, user=user, content_text="Go.", name="newer", is_master=True
    )

    record = calculate_ats_alignment(
        db=db, current_user=user, job_id=job.id, resume_version_id=older.id
    )

    assert record.resume_version_id == older.id


def test_other_users_resume_version_id_raises_not_found(db):
    owner = make_user(db, label="owner")
    intruder = make_user(db, label="intruder")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    owners_version = make_resume_version(
        db, user=owner, content_text="Python."
    )

    with pytest.raises(ATSAlignmentServiceError) as exc_info:
        calculate_ats_alignment(
            db=db,
            current_user=intruder,
            job_id=job.id,
            resume_version_id=owners_version.id,
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_job_not_found_raises_404(db):
    user = make_user(db, label="no-job")

    with pytest.raises(ATSAlignmentServiceError) as exc_info:
        calculate_ats_alignment(db=db, current_user=user, job_id=uuid4())

    assert exc_info.value.status_code == 404


def test_no_resume_raises_404(db):
    user = make_user(db, label="no-resume")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    with pytest.raises(ATSAlignmentServiceError) as exc_info:
        calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert exc_info.value.status_code == 404


def test_empty_resume_text_raises_422(db):
    user = make_user(db, label="empty-resume")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])
    make_resume_version(db, user=user, content_text="   ")

    with pytest.raises(ATSAlignmentServiceError) as exc_info:
        calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert exc_info.value.status_code == 422


def test_no_analyzable_requirements_raises_422(db):
    user = make_user(db, label="no-requirements")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Python developer.")
    make_requirement_intelligence(db, job=job, user=user, requirements=[])

    with pytest.raises(ATSAlignmentServiceError) as exc_info:
        calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------

def test_get_latest_ats_alignment_is_scoped_to_user(db):
    user_a = make_user(db, label="a")
    user_b = make_user(db, label="b")
    job = make_job(db)
    make_job_intelligence(db, job=job, required_skills=[skill_item("python")])

    make_resume_version(db, user=user_a, content_text="Python developer.")
    calculate_ats_alignment(db=db, current_user=user_a, job_id=job.id)

    result_for_b = get_latest_ats_alignment(
        db, user_id=user_b.id, job_id=job.id
    )

    assert result_for_b is None

    result_for_a = get_latest_ats_alignment(
        db, user_id=user_a.id, job_id=job.id
    )
    assert result_for_a is not None


def test_get_latest_ats_alignment_never_computes(db):
    user = make_user(db, label="read-only")
    job = make_job(db)

    result = get_latest_ats_alignment(db, user_id=user.id, job_id=job.id)

    assert result is None
