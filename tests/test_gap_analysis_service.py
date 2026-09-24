"""DB-backed tests for the Gap Analysis orchestration service (AJI-015)."""

from uuid import uuid4

import pytest

from apps.api.models import (
    Company,
    GapAnalysis,
    Job,
    JobIntelligence,
    Preference,
    Profile,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services.gap_analysis import service as gap_analysis_service
from apps.api.services.gap_analysis.service import (
    GapAnalysisServiceError,
    generate_gap_analysis,
    get_latest_gap_analysis,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint

from tests.support.requirement_intelligence import (
    make_requirement_intelligence,
    ri_skill_item,
)


class FakeGapAnalysisProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, response=None):
        self._response = response if response is not None else {"gaps": []}
        self.calls = []

    def generate_gap_suggestions(self, *, gap_candidates, job_context):
        self.calls.append((gap_candidates, job_context))
        return self._response


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
        name="Gap Analysis Test Co",
        normalized_name="gap analysis test co",
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
        requirements="5+ years of Rust experience required. SQL is a plus.",
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
        "required_experience": [],
        "preferred_experience": [],
        "education": [],
        "certifications": [],
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


@pytest.fixture(autouse=True)
def fake_job_intelligence_provider(monkeypatch):
    class FakeJobIntelligenceProvider:
        provider_name = "fake"
        model_name = "fake-model"

        def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
            return {}

    monkeypatch.setattr(
        "apps.api.services.job_intelligence.service.create_job_intelligence_provider",
        lambda: FakeJobIntelligenceProvider(),
    )


@pytest.fixture
def fake_gap_provider(monkeypatch):
    provider = FakeGapAnalysisProvider()
    monkeypatch.setattr(
        gap_analysis_service,
        "create_gap_analysis_provider",
        lambda: provider,
    )
    return provider


# ---------------------------------------------------------------------------
# Happy path: gaps come from ATS Alignment, never re-scored
# ---------------------------------------------------------------------------

def test_gap_analysis_reuses_ats_alignment_gaps(db, fake_gap_provider):
    user = make_user(db, label="happy")
    job = make_job(db)
    make_resume_version(
        db, user=user, content_text="Experienced engineer. Skills: SQL."
    )
    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[
            ri_skill_item("rust"),
            ri_skill_item("sql", importance="preferred"),
        ],
    )

    record = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert record.user_id == user.id
    assert record.job_id == job.id
    assert record.ats_alignment_id is not None

    gap_requirement_ids = {gap["requirement_id"] for gap in record.result["gaps"]}
    # Rust: no resume evidence -> missing gap. SQL: skills-section-only
    # mention -> partial gap. Neither status was recomputed here; both
    # came straight from the ATS Alignment engine.
    assert "req-skill-rust" in gap_requirement_ids

    for gap in record.result["gaps"]:
        if gap["requirement_id"] == "req-skill-rust":
            assert gap["status"] == "missing"
            assert gap["suggestion_type"] == "ADD_IF_TRUE"
            assert gap["resume_evidence"] is None


def test_no_gaps_when_ats_alignment_fully_matches(db, fake_gap_provider):
    user = make_user(db, label="full-match", years_experience=6)
    job = make_job(db)
    make_resume_version(
        db, user=user, content_text="Rust engineer. Skills: Rust. Used Rust daily."
    )
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    record = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert record.result["gaps"] == []
    assert record.must_have_gap_count == 0
    assert record.generation_status == "complete"


def test_gap_analysis_persists_ai_derived_explanations_when_valid(db, monkeypatch):
    user = make_user(db, label="ai-valid")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Engineer.")
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    provider = FakeGapAnalysisProvider(
        response={
            "gaps": [
                {
                    "requirement_id": "req-skill-rust",
                    "explanation": "Rust has no resume support.",
                    "explanation_evidence": "rust required.",
                    "suggestion_text": (
                        "If you have Rust experience, consider adding it."
                    ),
                    "confidence": "high",
                }
            ]
        }
    )
    monkeypatch.setattr(
        gap_analysis_service, "create_gap_analysis_provider", lambda: provider
    )

    record = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    gap = record.result["gaps"][0]
    assert gap["explanation_source"] == "ai"
    assert gap["suggestion_source"] == "ai"
    assert record.model_provider == "fake"
    assert record.generation_status == "complete"


def test_gap_analysis_degrades_to_partial_when_ai_call_fails(db, monkeypatch):
    class FailingProvider:
        provider_name = "fake"
        model_name = "fake-model"

        def generate_gap_suggestions(self, *, gap_candidates, job_context):
            raise RuntimeError("provider exploded")

    user = make_user(db, label="ai-fails")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Engineer.")
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    monkeypatch.setattr(
        gap_analysis_service, "create_gap_analysis_provider", lambda: FailingProvider()
    )

    record = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert record.generation_status == "partial"
    gap = record.result["gaps"][0]
    assert gap["explanation_source"] == "deterministic"
    assert gap["suggestion_source"] == "deterministic"
    assert gap["suggestion_type"] == "ADD_IF_TRUE"


# ---------------------------------------------------------------------------
# Idempotency / versioning
# ---------------------------------------------------------------------------

def test_same_inputs_reuse_existing_gap_analysis(db, fake_gap_provider):
    user = make_user(db, label="idempotent")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Engineer.")
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    first = generate_gap_analysis(db=db, current_user=user, job_id=job.id)
    second = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert first.id == second.id
    row_count = (
        db.query(GapAnalysis)
        .filter(GapAnalysis.user_id == user.id, GapAnalysis.job_id == job.id)
        .count()
    )
    assert row_count == 1


def test_gap_analysis_calls_ai_provider_exactly_once_per_new_analysis(
    db, fake_gap_provider
):
    user = make_user(db, label="single-ai-call")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Engineer.")
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    generate_gap_analysis(db=db, current_user=user, job_id=job.id)
    generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert len(fake_gap_provider.calls) == 1


def test_changed_resume_version_creates_new_gap_analysis(db, fake_gap_provider):
    user = make_user(db, label="resume-change")
    job = make_job(db)
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    make_resume_version(
        db, user=user, content_text="Engineer.", name="v1", is_master=True
    )
    first = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    make_resume_version(
        db, user=user, content_text="Rust engineer.", name="v2", is_master=True
    )
    second = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.resume_version_id != first.resume_version_id


def test_new_ats_alignment_snapshot_creates_new_gap_analysis(db, fake_gap_provider):
    user = make_user(db, label="ats-change")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Engineer.")

    make_job_intelligence(
        db,
        job=job,
        required_skills=[skill_item("rust")],
        content_fingerprint="fp-1",
    )
    first = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    make_job_intelligence(
        db,
        job=job,
        required_skills=[skill_item("rust"), skill_item("go")],
        content_fingerprint="fp-2",
    )
    second = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.ats_alignment_id != first.ats_alignment_id


def test_bumped_analyzer_version_creates_new_gap_analysis(db, monkeypatch, fake_gap_provider):
    user = make_user(db, label="analyzer-version")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Engineer.")
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    first = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    monkeypatch.setattr(gap_analysis_service, "ANALYZER_VERSION", "9.9.9")
    second = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert second.id != first.id
    assert second.analyzer_version == "9.9.9"


def test_gap_analysis_is_immutable_across_regeneration(db, fake_gap_provider):
    """Regenerating never mutates a prior row's stored result."""
    user = make_user(db, label="immutable")
    job = make_job(db)
    make_resume_version(db, user=user, content_text="Engineer.", name="v1")
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    first = generate_gap_analysis(db=db, current_user=user, job_id=job.id)
    first_result_snapshot = dict(first.result)

    make_resume_version(db, user=user, content_text="Rust engineer.", name="v2")
    generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    db.refresh(first)
    assert first.result == first_result_snapshot


# ---------------------------------------------------------------------------
# Error propagation from ATS Alignment (never reimplemented here)
# ---------------------------------------------------------------------------

def test_job_not_found_raises_404(db, fake_gap_provider):
    user = make_user(db, label="no-job")

    with pytest.raises(GapAnalysisServiceError) as exc_info:
        generate_gap_analysis(db=db, current_user=user, job_id=uuid4())

    assert exc_info.value.status_code == 404


def test_no_resume_raises_404(db, fake_gap_provider):
    user = make_user(db, label="no-resume")
    job = make_job(db)
    make_requirement_intelligence(db, job=job, user=user, requirements=[ri_skill_item("rust")])

    with pytest.raises(GapAnalysisServiceError) as exc_info:
        generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    assert exc_info.value.status_code == 404


def test_other_users_resume_version_id_raises_404(db, fake_gap_provider):
    owner = make_user(db, label="owner")
    intruder = make_user(db, label="intruder")
    job = make_job(db)

    owners_version = make_resume_version(db, user=owner, content_text="Engineer.")

    with pytest.raises(GapAnalysisServiceError) as exc_info:
        generate_gap_analysis(
            db=db,
            current_user=intruder,
            job_id=job.id,
            resume_version_id=owners_version.id,
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------

def test_get_latest_gap_analysis_is_scoped_to_user(db, fake_gap_provider):
    user_a = make_user(db, label="a")
    user_b = make_user(db, label="b")
    job = make_job(db)
    make_requirement_intelligence(
        db, job=job, user=user_a, requirements=[ri_skill_item("rust")]
    )

    make_resume_version(db, user=user_a, content_text="Engineer.")
    generate_gap_analysis(db=db, current_user=user_a, job_id=job.id)

    assert get_latest_gap_analysis(db, user_id=user_b.id, job_id=job.id) is None
    assert get_latest_gap_analysis(db, user_id=user_a.id, job_id=job.id) is not None


def test_get_latest_gap_analysis_never_computes(db):
    user = make_user(db, label="read-only")
    job = make_job(db)

    result = get_latest_gap_analysis(db, user_id=user.id, job_id=job.id)

    assert result is None
