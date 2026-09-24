"""AJI-020C integration tests: ATS Alignment consuming the persisted
AJI-020A/B Requirement Intelligence contract.

Complements test_ats_alignment_service.py (which already covers the
core happy path, idempotency, and versioning against
RequirementIntelligence) with the specific AJI-020C checklist: relationship
surfacing (AND/OR/MIN_COUNT/EQUIVALENT), screening-constraint separation,
importance/hard_requirement independence, technology-boundary
protection surviving the full pipeline, requirement identity, and the
fallback/failure policy for an unavailable Requirement Intelligence
snapshot.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api.models import Company, Job, Preference, Profile, Resume, ResumeVersion, User
from apps.api.services.ats_alignment_service import (
    ATSAlignmentServiceError,
    calculate_ats_alignment,
)
from apps.api.services.requirement_intelligence.persistence_service import (
    RequirementIntelligencePersistenceError,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint

from tests.support.requirement_intelligence import (
    make_requirement_intelligence,
    ri_skill_item,
)


def _make_user(db, *, years_experience: float | None = 5.0) -> User:
    user = User(
        id=uuid4(),
        email=f"ri-ats-integration-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id, years_experience=years_experience))
    db.add(Preference(id=uuid4(), user_id=user.id))
    db.flush()

    return user


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


def _make_job(db, **overrides) -> Job:
    company = Company(
        id=uuid4(),
        name="RI-ATS Integration Co",
        normalized_name="ri-ats integration co",
    )
    db.add(company)
    db.flush()

    defaults = dict(
        id=uuid4(),
        company_id=company.id,
        title="Backend Engineer",
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="Join our team.",
        requirements="Python required.",
        source="test",
        source_url=f"https://example.com/jobs/{uuid4()}",
    )
    defaults.update(overrides)

    job = Job(**defaults)
    db.add(job)
    db.flush()

    return job


# ---------------------------------------------------------------------------
# Relationships: surfaced descriptively, never folded into scoring
# ---------------------------------------------------------------------------

def test_or_relationship_is_surfaced_and_members_scored_independently(db):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python"), ri_skill_item("java")],
        relationships=[
            {
                "id": "grp-0001",
                "relationship": "OR",
                "member_ids": ["req-skill-python", "req-skill-java"],
                "description": "Either Python or Java satisfies this clause.",
                "evidence_text": "Python or Java required.",
            }
        ],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    statuses = {
        item["requirement_id"]: item["status"]
        for item in record.result["requirement_results"]
    }
    assert statuses["req-skill-python"] == "matched"
    assert statuses["req-skill-java"] == "missing"

    relationships = record.result["relationships"]
    assert len(relationships) == 1
    assert relationships[0]["relationship"] == "OR"
    assert set(relationships[0]["member_requirement_ids"]) == {
        "req-skill-python",
        "req-skill-java",
    }
    # Never collapsed into a single derived requirement/verdict.
    assert len(record.result["requirement_results"]) == 2


def test_and_relationship_is_surfaced_without_altering_individual_status(db):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python"), ri_skill_item("django")],
        relationships=[
            {
                "id": "grp-0001",
                "relationship": "AND",
                "member_ids": ["req-skill-python", "req-skill-django"],
                "description": "Both Python and Django are needed.",
                "evidence_text": "Python and Django required.",
            }
        ],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    statuses = {
        item["requirement_id"]: item["status"]
        for item in record.result["requirement_results"]
    }
    # Django is missing but Python is matched - AND is never used to drag
    # Python's own verdict down, and is never converted into an OR either.
    assert statuses["req-skill-python"] == "matched"
    assert statuses["req-skill-django"] == "missing"
    assert record.result["relationships"][0]["relationship"] == "AND"


def test_min_count_relationship_preserves_explicit_minimum(db):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[
            ri_skill_item("python", importance="preferred"),
            ri_skill_item("java", importance="preferred"),
            ri_skill_item("go", importance="preferred"),
        ],
        relationships=[
            {
                "id": "grp-0001",
                "relationship": "MIN_COUNT",
                "member_ids": [
                    "req-skill-python",
                    "req-skill-java",
                    "req-skill-go",
                ],
                "minimum_count": 2,
                "description": "At least 2 of these are required.",
                "evidence_text": "At least 2 of: Python, Java, Go.",
            }
        ],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    group = record.result["relationships"][0]
    assert group["relationship"] == "MIN_COUNT"
    assert group["minimum_count"] == 2
    assert len(group["member_requirement_ids"]) == 3
    # ATS never converts "3 of 5 technologies" into N mandatory
    # requirements - every member keeps its own independent category.
    categories = {
        item["requirement_id"]: item["category"]
        for item in record.result["requirement_results"]
    }
    assert all(category == "preferred" for category in categories.values())


def test_equivalent_relationship_is_not_general_similarity(db):
    """EQUIVALENT must represent an explicitly evidenced equivalence
    (e.g. "AWS or equivalent cloud platform experience"), never a
    generic "these are similar" judgment - and never duplicated into a
    second scored requirement."""
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="AWS certified engineer.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("aws")],
        relationships=[
            {
                "id": "grp-0001",
                "relationship": "EQUIVALENT",
                "member_ids": ["req-skill-aws"],
                "description": (
                    "AWS is interchangeable with a JD-stated equivalent "
                    "alternative."
                ),
                "evidence_text": "AWS or equivalent cloud platform experience.",
            }
        ],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert len(record.result["requirement_results"]) == 1
    group = record.result["relationships"][0]
    assert group["relationship"] == "EQUIVALENT"
    assert group["member_requirement_ids"] == ["req-skill-aws"]


# ---------------------------------------------------------------------------
# Screening constraints: separate, never scored as technical requirements
# ---------------------------------------------------------------------------

def test_screening_constraints_never_appear_in_requirement_results(db):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python")],
        screening_constraints=[
            {
                "id": "scr-0001",
                "constraint_type": "background_check",
                "status": "required",
                "statement": "A background check is required.",
                "raw_text": "Background check required.",
            },
            {
                "id": "scr-0002",
                "constraint_type": "work_authorization",
                "status": "disqualifying",
                "statement": "Must be authorized to work.",
                "raw_text": "Must be authorized to work in the US.",
            },
        ],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert len(record.result["requirement_results"]) == 1
    assert record.result["must_have_total"] == 1

    constraint_types = {
        c["constraint_type"] for c in record.result["screening_constraints"]
    }
    assert constraint_types == {"background_check", "work_authorization"}

    # Never mixed into the scored list under any requirement_type.
    scored_types = {
        item["requirement_type"] for item in record.result["requirement_results"]
    }
    assert "background_check" not in scored_types
    assert "work_authorization" not in scored_types


# ---------------------------------------------------------------------------
# Importance / hard_requirement independence
# ---------------------------------------------------------------------------

def test_required_importance_does_not_imply_hard_requirement(db):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python", importance="required")],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    item = record.result["requirement_results"][0]
    assert item["category"] == "must_have"
    assert item["hard_requirement"] is False


def test_hard_requirement_true_is_preserved_but_never_changes_scoring(db):
    """No approved product rule exists for hard_requirement affecting
    score - AJI-020C carries the field through as metadata only. Two
    otherwise-identical missing requirements, one hard_requirement=True,
    must score identically."""
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Marketing generalist.")

    soft = {**ri_skill_item("python", importance="required"), "id": "req-soft"}
    hard = {
        **ri_skill_item("java", importance="required"),
        "id": "req-hard",
        "hard_requirement": True,
    }

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[soft, hard],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    by_id = {item["requirement_id"]: item for item in record.result["requirement_results"]}
    assert by_id["req-soft"]["hard_requirement"] is False
    assert by_id["req-hard"]["hard_requirement"] is True
    # Both missing, both weighted identically - no invented penalty.
    assert by_id["req-soft"]["status"] == by_id["req-hard"]["status"] == "missing"
    assert record.overall_score == 0.0


def test_contextual_and_informational_items_are_never_scored(db):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    contextual = {
        **ri_skill_item("kubernetes", importance="contextual"),
        "id": "req-contextual",
    }
    informational = {
        "id": "req-info",
        "requirement_type": "responsibility",
        "importance": "informational",
        "statement": "Build and maintain services",
        "canonical_terms": [],
        "raw_text": "Build and maintain services",
        "confidence": "high",
    }

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python"), contextual, informational],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    scored_ids = {item["requirement_id"] for item in record.result["requirement_results"]}
    assert scored_ids == {"req-skill-python"}
    assert record.result["must_have_total"] == 1


# ---------------------------------------------------------------------------
# Requirement identity / provenance
# ---------------------------------------------------------------------------

def test_requirement_id_traces_back_to_the_original_ri_item(db):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    make_requirement_intelligence(
        db,
        job=job,
        user=user,
        requirements=[ri_skill_item("python", item_id="req-custom-id-123")],
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert record.result["requirement_results"][0]["requirement_id"] == (
        "req-custom-id-123"
    )


# ---------------------------------------------------------------------------
# Technology-boundary protection survives the full pipeline
# ---------------------------------------------------------------------------

def test_react_native_is_never_scored_as_plain_react_end_to_end(db):
    """Uses the real (deterministic-only) Requirement Intelligence
    extraction path, not a hand-crafted fixture, to prove the
    React-vs-React-Native protection AJI-020A implements survives all
    the way through to ATS Alignment's scored output."""
    user = _make_user(db)
    job = _make_job(
        db,
        description="Join our team.",
        requirements="3+ years of React Native experience required.",
    )
    _make_resume_version(
        db, user=user, content_text="Experienced React developer."
    )

    record = calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    canonical_skills = {
        item.get("requirement_text")
        for item in record.result["requirement_results"]
        if item["requirement_type"] == "skill"
    }
    assert "react" not in canonical_skills


# ---------------------------------------------------------------------------
# Fallback policy: no silent fallback to raw-JD parsing
# ---------------------------------------------------------------------------

def test_requirement_intelligence_unavailable_propagates_service_error(
    db, monkeypatch
):
    user = _make_user(db)
    job = _make_job(db)
    _make_resume_version(db, user=user, content_text="Python developer.")

    def _raise(*_args, **_kwargs):
        raise RequirementIntelligencePersistenceError(
            "Unable to extract Requirement Intelligence for this JD.",
            status_code=503,
        )

    monkeypatch.setattr(
        "apps.api.services.ats_alignment_service.generate_requirement_intelligence",
        _raise,
    )

    with pytest.raises(ATSAlignmentServiceError) as exc_info:
        calculate_ats_alignment(db=db, current_user=user, job_id=job.id)

    assert exc_info.value.status_code == 503
