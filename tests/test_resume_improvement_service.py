"""DB-backed tests for the Resume Improvement Approval & Recheck
orchestration service (AJI-021).

Covers the rules that can only be proven against a real database: the
original resume is never overwritten, the parent/child link is real,
duplicate approvals never create a second version, the recheck runs
against the same job with the new version, and a failed recheck never
costs the user that version.
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from apps.api.models import (
    AtsAlignmentResult,
    Company,
    GapAnalysis,
    Job,
    JobIntelligence,
    Preference,
    Profile,
    Resume,
    ResumeImprovement,
    ResumeVersion,
    User,
)
from apps.api.services.ats_alignment_service import ATSAlignmentServiceError
from apps.api.services.gap_analysis import service as gap_analysis_service
from apps.api.services.gap_analysis.service import generate_gap_analysis
from apps.api.services.resume_fingerprint import compute_content_fingerprint
from apps.api.services.resume_improvement import service as improvement_service
from apps.api.services.resume_improvement.service import (
    ResumeImprovementServiceError,
    create_resume_improvement,
    get_latest_resume_improvement,
    run_recheck,
)

from tests.support.requirement_intelligence import (
    make_requirement_intelligence,
    ri_skill_item,
)


RESUME_TEXT = """Jane Doe
jane@example.com

PROFESSIONAL EXPERIENCE
- Built billing services at Acme.

SKILLS
SQL
"""


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fake_ai_providers(monkeypatch):
    class FakeJobIntelligenceProvider:
        provider_name = "fake"
        model_name = "fake-model"

        def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
            return {}

    class FakeGapAnalysisProvider:
        provider_name = "fake"
        model_name = "fake-model"

        def generate_gap_suggestions(self, *, gap_candidates, job_context):
            return {"gaps": []}

    monkeypatch.setattr(
        "apps.api.services.job_intelligence.service."
        "create_job_intelligence_provider",
        lambda: FakeJobIntelligenceProvider(),
    )
    monkeypatch.setattr(
        gap_analysis_service,
        "create_gap_analysis_provider",
        lambda: FakeGapAnalysisProvider(),
    )


def make_user(db, *, label: str = "improve", years_experience: float = 5.0) -> User:
    user = User(
        id=uuid4(),
        email=f"{label}-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id, years_experience=years_experience))
    db.add(Preference(id=uuid4(), user_id=user.id))
    db.flush()
    db.refresh(user)

    return user


def make_resume_version(
    db,
    *,
    user: User,
    content_text: str = RESUME_TEXT,
    name: str = "Original",
) -> ResumeVersion:
    resume = Resume(
        id=uuid4(),
        user_id=user.id,
        filename="resume.pdf",
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
        original_filename="resume.pdf",
        storage_path=f"/tmp/{uuid4()}.pdf",
        is_master=True,
    )
    db.add(version)
    db.flush()

    return version


def make_job(db) -> Job:
    company = Company(
        id=uuid4(),
        name="Improvement Test Co",
        normalized_name="improvement test co",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Platform Engineer",
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="Kubernetes required. SQL is a plus.",
        requirements="Kubernetes required. SQL is a plus.",
        source="test",
        source_url=f"https://example.com/jobs/{uuid4()}",
    )
    db.add(job)
    db.flush()

    return job


def setup_gap_analysis(db, *, user: User) -> tuple[Job, ResumeVersion, GapAnalysis]:
    """Run the real Analyze -> Review pipeline up to a stored Gap
    Analysis, so improvement tests act on genuine gaps rather than a
    hand-written fixture."""
    job = make_job(db)
    parent = make_resume_version(db, user=user)
    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[
            ri_skill_item("kubernetes"),
            ri_skill_item("sql", importance="preferred"),
        ],
    )

    gap_analysis = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    return job, parent, gap_analysis


def approve_all(gap_analysis: GapAnalysis, *, text: str = "Ran Kubernetes in production.") -> list[dict]:
    return [
        {
            "requirement_id": gap["requirement_id"],
            "action": "approve",
            "truth_confirmed": True,
            "user_content": text,
        }
        for gap in gap_analysis.result["gaps"]
    ]



def create_and_recheck(db, *, user, job, gap_analysis, decisions=None):
    """Both explicit steps: create the version, then run the recheck.

    Creation no longer rechecks on its own (Figma 09's "Run recheck" is
    a separate user action), so any test asserting on a recheck outcome
    has to run it.
    """
    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=decisions if decisions is not None else approve_all(gap_analysis),
    )
    return run_recheck(
        db=db,
        current_user=user,
        job_id=job.id,
        improvement_id=record.id,
    )


# ---------------------------------------------------------------------------
# Happy path: create a child version and recheck it
# ---------------------------------------------------------------------------

def test_approving_creates_a_child_version_and_rechecks_the_same_job(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    assert gap_analysis.result["gaps"], "fixture should produce real gaps"

    record = create_and_recheck(
        db,
        user=user,
        job=job,
        gap_analysis=gap_analysis,
        decisions=approve_all(gap_analysis),
    )

    assert record.parent_resume_version_id == parent.id
    assert record.child_resume_version_id != parent.id
    assert record.recheck_status == "complete"
    assert record.recheck_ats_alignment_id is not None

    recheck = db.get(AtsAlignmentResult, record.recheck_ats_alignment_id)
    # Same job, new version - the ticket's recheck rule.
    assert recheck.job_id == job.id
    assert recheck.resume_version_id == record.child_resume_version_id
    assert recheck.user_id == user.id


def test_the_original_version_is_never_modified(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    original_text = parent.content_text
    original_fingerprint = parent.content_fingerprint
    original_storage_path = parent.storage_path
    original_name = parent.name

    create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    db.refresh(parent)

    assert parent.content_text == original_text
    assert parent.content_fingerprint == original_fingerprint
    assert parent.storage_path == original_storage_path
    assert parent.name == original_name
    assert parent.is_master is True
    assert parent.parent_version_id is None
    assert parent.source == "upload"


def test_the_child_records_a_real_parent_child_relationship(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    child = db.get(ResumeVersion, record.child_resume_version_id)

    assert child.parent_version_id == parent.id
    assert child.source == "improvement"
    assert child.resume_id == parent.resume_id
    # Approving suggestions for one job never repoints the master resume.
    assert child.is_master is False
    # No uploaded document exists for a generated version.
    assert child.storage_path is None
    assert child.content_text.startswith(parent.content_text.rstrip())


def test_the_child_contains_only_the_users_own_added_text(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(
            gap_analysis, text="Operated Kubernetes clusters at Acme."
        ),
    )

    child = db.get(ResumeVersion, record.child_resume_version_id)
    added = child.content_text[len(parent.content_text.rstrip()) :]

    assert "Operated Kubernetes clusters at Acme." in added

    # The Gap Analysis suggestion strings are never copied into the
    # resume - they are advice to the user, not resume content.
    for gap in gap_analysis.result["gaps"]:
        assert gap["suggestion_text"] not in child.content_text
        assert gap["explanation"] not in child.content_text


def test_the_recheck_reflects_the_added_evidence_in_the_comparison(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    kubernetes_gap = next(
        gap
        for gap in gap_analysis.result["gaps"]
        if gap["requirement_id"] == "req-skill-kubernetes"
    )
    assert kubernetes_gap["status"] == "missing"

    record = create_and_recheck(
        db,
        user=user,
        job=job,
        gap_analysis=gap_analysis,
        decisions=[
            {
                "requirement_id": "req-skill-kubernetes",
                "action": "approve",
                "truth_confirmed": True,
                "user_content": "Operated Kubernetes clusters in production.",
            }
        ],
    )

    comparison = record.result["comparison"]

    assert comparison["baseline_ats_alignment_id"] == str(
        gap_analysis.ats_alignment_id
    )
    assert comparison["recheck_resume_version_id"] == str(
        record.child_resume_version_id
    )

    transition = next(
        item
        for item in comparison["transitions"]
        if item["requirement_id"] == "req-skill-kubernetes"
    )
    assert transition["before_status"] == "missing"
    assert transition["after_status"] == "matched"
    assert transition["direction"] == "improved"
    assert transition["was_approved"] is True
    assert comparison["score_delta"] > 0


# ---------------------------------------------------------------------------
# Duplicate prevention
# ---------------------------------------------------------------------------

def test_resubmitting_the_same_approvals_reuses_the_existing_record(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)
    decisions = approve_all(gap_analysis)

    first = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=decisions,
    )
    second = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=decisions,
    )

    assert first.id == second.id
    assert first.child_resume_version_id == second.child_resume_version_id

    version_count = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.resume_id == parent.resume_id)
        .count()
    )
    # The original plus exactly one generated child - never two.
    assert version_count == 2


def test_reordering_the_same_approvals_still_reuses_the_record(db):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)
    decisions = approve_all(gap_analysis)

    if len(decisions) < 2:
        pytest.skip("needs at least two gaps to reorder")

    first = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=decisions,
    )
    second = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=list(reversed(decisions)),
    )

    assert first.id == second.id


def test_a_different_approval_set_creates_a_separate_version(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    first = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=[
            {
                "requirement_id": "req-skill-kubernetes",
                "action": "approve",
                "truth_confirmed": True,
                "user_content": "Operated Kubernetes clusters in production.",
            }
        ],
    )
    second = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=[
            {
                "requirement_id": "req-skill-kubernetes",
                "action": "approve",
                "truth_confirmed": True,
                "user_content": "Ran Kubernetes for the billing platform.",
            }
        ],
    )

    assert first.id != second.id
    assert first.child_resume_version_id != second.child_resume_version_id

    names = {
        row[0]
        for row in db.query(ResumeVersion.name)
        .filter(ResumeVersion.resume_id == parent.resume_id)
        .all()
    }
    assert {"Original", "Improved 1", "Improved 2"} == names


def test_the_database_itself_rejects_a_duplicate_fingerprint(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    # Inside its own SAVEPOINT so the failed insert can be undone
    # without unwinding the record created above.
    savepoint = db.begin_nested()

    duplicate = ResumeImprovement(
        user_id=record.user_id,
        job_id=record.job_id,
        gap_analysis_id=record.gap_analysis_id,
        baseline_ats_alignment_id=record.baseline_ats_alignment_id,
        parent_resume_version_id=record.parent_resume_version_id,
        child_resume_version_id=record.child_resume_version_id,
        approval_fingerprint=record.approval_fingerprint,
        engine_version=record.engine_version,
        recheck_status="pending",
        result=record.result,
    )
    db.add(duplicate)

    with pytest.raises(IntegrityError):
        db.flush()

    savepoint.rollback()

    # The original record is untouched by the rejected duplicate.
    assert db.get(ResumeImprovement, record.id) is not None


# ---------------------------------------------------------------------------
# Approval rules, enforced server-side
# ---------------------------------------------------------------------------

def test_a_submission_with_no_approvals_is_rejected_server_side(db):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)

    with pytest.raises(ResumeImprovementServiceError) as exc:
        create_resume_improvement(
            db=db,
            current_user=user,
            job_id=job.id,
            gap_analysis_id=gap_analysis.id,
            decisions=[
                {"requirement_id": gap["requirement_id"], "action": "skip"}
                for gap in gap_analysis.result["gaps"]
            ],
        )

    assert exc.value.status_code == 422
    assert exc.value.code == "no_approvals"


def test_an_unconfirmed_add_if_true_approval_is_rejected_server_side(db):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)

    with pytest.raises(ResumeImprovementServiceError) as exc:
        create_resume_improvement(
            db=db,
            current_user=user,
            job_id=job.id,
            gap_analysis_id=gap_analysis.id,
            decisions=[
                {
                    "requirement_id": "req-skill-kubernetes",
                    "action": "approve",
                    "truth_confirmed": False,
                    "user_content": "Operated Kubernetes clusters.",
                }
            ],
        )

    assert exc.value.status_code == 422
    assert exc.value.code == "truth_confirmation_required"


def test_a_rejected_submission_creates_no_version_at_all(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    before = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.resume_id == parent.resume_id)
        .count()
    )

    with pytest.raises(ResumeImprovementServiceError):
        create_resume_improvement(
            db=db,
            current_user=user,
            job_id=job.id,
            gap_analysis_id=gap_analysis.id,
            decisions=[
                {
                    "requirement_id": "req-skill-kubernetes",
                    "action": "approve",
                    "truth_confirmed": False,
                    "user_content": "Operated Kubernetes clusters.",
                }
            ],
        )

    after = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.resume_id == parent.resume_id)
        .count()
    )
    assert before == after


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

def test_another_users_gap_analysis_is_not_found(db):
    owner = make_user(db, label="owner")
    intruder = make_user(db, label="intruder")
    job, _, gap_analysis = setup_gap_analysis(db, user=owner)

    with pytest.raises(ResumeImprovementServiceError) as exc:
        create_resume_improvement(
            db=db,
            current_user=intruder,
            job_id=job.id,
            gap_analysis_id=gap_analysis.id,
            decisions=approve_all(gap_analysis),
        )

    assert exc.value.status_code == 404
    assert exc.value.code == "gap_analysis_not_found"


def test_a_gap_analysis_from_a_different_job_is_not_found(db):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)
    other_job = make_job(db)

    with pytest.raises(ResumeImprovementServiceError) as exc:
        create_resume_improvement(
            db=db,
            current_user=user,
            job_id=other_job.id,
            gap_analysis_id=gap_analysis.id,
            decisions=approve_all(gap_analysis),
        )

    assert exc.value.status_code == 404


def test_the_latest_lookup_never_returns_another_users_record(db):
    owner = make_user(db, label="owner")
    intruder = make_user(db, label="intruder")
    job, _, gap_analysis = setup_gap_analysis(db, user=owner)

    create_resume_improvement(
        db=db,
        current_user=owner,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    assert (
        get_latest_resume_improvement(db, user_id=intruder.id, job_id=job.id)
        is None
    )
    assert (
        get_latest_resume_improvement(db, user_id=owner.id, job_id=job.id)
        is not None
    )


# ---------------------------------------------------------------------------
# A failed recheck never costs the user their version
# ---------------------------------------------------------------------------

def test_the_new_version_survives_a_failed_recheck(db, monkeypatch):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    def explode(**kwargs):
        raise ATSAlignmentServiceError(
            "Requirement Intelligence is unavailable.", status_code=503
        )

    monkeypatch.setattr(improvement_service, "calculate_ats_alignment", explode)

    record = create_and_recheck(
        db,
        user=user,
        job=job,
        gap_analysis=gap_analysis,
        decisions=approve_all(gap_analysis),
    )

    assert record.recheck_status == "failed"
    assert record.recheck_error == "Requirement Intelligence is unavailable."
    assert record.recheck_ats_alignment_id is None
    assert record.result.get("comparison") is None

    # The version the user approved is still there, fully intact.
    child = db.get(ResumeVersion, record.child_resume_version_id)
    assert child is not None
    assert child.parent_version_id == parent.id
    assert child.source == "improvement"


def test_an_unexpected_recheck_failure_does_not_leak_internal_detail(db, monkeypatch):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)

    def explode(**kwargs):
        raise RuntimeError("psycopg connection string user=secret host=internal")

    monkeypatch.setattr(improvement_service, "calculate_ats_alignment", explode)

    record = create_and_recheck(
        db,
        user=user,
        job=job,
        gap_analysis=gap_analysis,
        decisions=approve_all(gap_analysis),
    )

    assert record.recheck_status == "failed"
    assert record.recheck_error == "The recheck could not be completed."
    assert "secret" not in (record.recheck_error or "")


def test_a_failed_recheck_can_be_retried_without_creating_a_version(db, monkeypatch):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    def explode(**kwargs):
        raise ATSAlignmentServiceError("Temporarily unavailable.", status_code=503)

    monkeypatch.setattr(improvement_service, "calculate_ats_alignment", explode)

    record = create_and_recheck(
        db,
        user=user,
        job=job,
        gap_analysis=gap_analysis,
        decisions=approve_all(gap_analysis),
    )
    assert record.recheck_status == "failed"

    child_version_id = record.child_resume_version_id

    monkeypatch.undo()

    retried = run_recheck(
        db=db,
        current_user=user,
        job_id=job.id,
        improvement_id=record.id,
    )

    assert retried.id == record.id
    assert retried.recheck_status == "complete"
    assert retried.recheck_ats_alignment_id is not None
    assert retried.recheck_error is None
    assert retried.result["comparison"] is not None
    # No second version was created by the retry.
    assert retried.child_resume_version_id == child_version_id
    assert (
        db.query(ResumeVersion)
        .filter(ResumeVersion.resume_id == parent.resume_id)
        .count()
        == 2
    )


def test_retrying_a_completed_recheck_never_repoints_it(db):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)

    record = create_and_recheck(
        db,
        user=user,
        job=job,
        gap_analysis=gap_analysis,
        decisions=approve_all(gap_analysis),
    )
    original_recheck_id = record.recheck_ats_alignment_id

    retried = run_recheck(
        db=db,
        current_user=user,
        job_id=job.id,
        improvement_id=record.id,
    )

    assert retried.recheck_ats_alignment_id == original_recheck_id


def test_another_user_cannot_retry_someone_elses_recheck(db):
    owner = make_user(db, label="owner")
    intruder = make_user(db, label="intruder")
    job, _, gap_analysis = setup_gap_analysis(db, user=owner)

    record = create_resume_improvement(
        db=db,
        current_user=owner,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    with pytest.raises(ResumeImprovementServiceError) as exc:
        run_recheck(
            db=db,
            current_user=intruder,
            job_id=job.id,
            improvement_id=record.id,
        )

    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# The ATS scoring path is reused, not duplicated
# ---------------------------------------------------------------------------

def test_the_recheck_is_an_ordinary_ats_alignment_row(db):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)

    baseline = db.get(AtsAlignmentResult, gap_analysis.ats_alignment_id)

    record = create_and_recheck(
        db,
        user=user,
        job=job,
        gap_analysis=gap_analysis,
        decisions=approve_all(gap_analysis),
    )

    recheck = db.get(AtsAlignmentResult, record.recheck_ats_alignment_id)

    # Same engine, same scoring formula, same Requirement Intelligence
    # snapshot - only the resume version differs.
    assert recheck.engine_version == baseline.engine_version
    assert recheck.result["scoring_version"] == baseline.result["scoring_version"]
    assert (
        recheck.requirement_intelligence_id
        == baseline.requirement_intelligence_id
    )
    assert recheck.resume_version_id != baseline.resume_version_id


def test_job_intelligence_and_gap_analysis_rows_are_untouched(db):
    user = make_user(db)
    job, _, gap_analysis = setup_gap_analysis(db, user=user)

    gap_result_before = dict(gap_analysis.result)
    job_intelligence_count_before = (
        db.query(JobIntelligence).filter(JobIntelligence.job_id == job.id).count()
    )
    gap_count_before = (
        db.query(GapAnalysis).filter(GapAnalysis.job_id == job.id).count()
    )

    create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    db.refresh(gap_analysis)

    assert gap_analysis.result == gap_result_before
    assert (
        db.query(JobIntelligence).filter(JobIntelligence.job_id == job.id).count()
        == job_intelligence_count_before
    )
    assert (
        db.query(GapAnalysis).filter(GapAnalysis.job_id == job.id).count()
        == gap_count_before
    )


# ---------------------------------------------------------------------------
# Creating a version does not recheck: "Run recheck" is a separate step
# ---------------------------------------------------------------------------

def test_creating_a_version_does_not_run_the_recheck(db, monkeypatch):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    calls = []

    def spy(**kwargs):
        calls.append(kwargs)
        raise AssertionError("the recheck must not run during creation")

    monkeypatch.setattr(improvement_service, "calculate_ats_alignment", spy)

    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    assert calls == []
    assert record.recheck_status == "pending"
    assert record.recheck_ats_alignment_id is None
    assert record.recheck_error is None
    assert record.result.get("comparison") is None

    # The version itself is already fully created and committed.
    child = db.get(ResumeVersion, record.child_resume_version_id)
    assert child is not None
    assert child.parent_version_id == parent.id


def test_a_pending_version_stays_persisted_if_the_recheck_is_never_run(db):
    """Leaving the page without running the recheck must not cost the
    user the version they approved."""
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    # Simulate coming back later: re-read everything from the database.
    db.expire_all()

    reloaded = get_latest_resume_improvement(db, user_id=user.id, job_id=job.id)
    assert reloaded is not None
    assert reloaded.id == record.id
    assert reloaded.recheck_status == "pending"

    child = db.get(ResumeVersion, reloaded.child_resume_version_id)
    assert child is not None
    assert child.source == "improvement"
    assert child.content_text.startswith(parent.content_text.rstrip())

    # And the recheck can still be run afterwards.
    rechecked = run_recheck(
        db=db,
        current_user=user,
        job_id=job.id,
        improvement_id=reloaded.id,
    )
    assert rechecked.recheck_status == "complete"
    assert rechecked.child_resume_version_id == child.id


def test_run_recheck_uses_the_same_job_and_the_new_version(db):
    user = make_user(db)
    job, parent, gap_analysis = setup_gap_analysis(db, user=user)

    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )
    rechecked = run_recheck(
        db=db,
        current_user=user,
        job_id=job.id,
        improvement_id=record.id,
    )

    recheck = db.get(AtsAlignmentResult, rechecked.recheck_ats_alignment_id)
    assert recheck.job_id == job.id
    assert recheck.resume_version_id == record.child_resume_version_id
    assert recheck.resume_version_id != parent.id


def test_the_record_carries_the_real_parent_version_name(db):
    """Lineage is displayed from stored data, never from a hardcoded
    placeholder — so a non-default parent name must survive."""
    user = make_user(db)
    job = make_job(db)
    parent = make_resume_version(db, user=user, name="Senior SRE CV")
    make_requirement_intelligence(
        db, job=job, user=user, requirements=[ri_skill_item("kubernetes")]
    )
    gap_analysis = generate_gap_analysis(db=db, current_user=user, job_id=job.id)

    record = create_resume_improvement(
        db=db,
        current_user=user,
        job_id=job.id,
        gap_analysis_id=gap_analysis.id,
        decisions=approve_all(gap_analysis),
    )

    assert record.result["parent_resume_version_name"] == "Senior SRE CV"
    assert record.result["child_resume_version_name"] == "Improved 1"
    assert record.parent_resume_version_id == parent.id
