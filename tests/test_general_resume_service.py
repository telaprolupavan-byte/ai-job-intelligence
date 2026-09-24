"""AJI-027 General Resume Intelligence: DB-level guarantees."""

from uuid import uuid4

import pytest

from apps.api.models import (
    GeneralResumeAssessment,
    GeneralResumeReview,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services.general_resume import service as general_service
from apps.api.services.general_resume.service import (
    GeneralResumeServiceError,
    assess_resume_version,
    compute_readiness,
    create_review,
    get_current_assessment,
    run_review_recheck,
    serialize_assessment,
    serialize_review,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint

from tests.general_resume_fixtures import (
    STRONG_RESUME,
    WEAK_BULLET_1,
    WEAK_RESUME,
)


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self):
        self.calls = 0

    def generate_improvement_explanations(self, *, items):
        self.calls += 1
        return {"items": []}


class FailingProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_improvement_explanations(self, *, items):
        raise RuntimeError("provider down")


@pytest.fixture
def fake_provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(
        general_service, "create_general_resume_provider", lambda: provider
    )
    return provider


def make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"general-resume-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def make_version(db, user, text=WEAK_RESUME) -> ResumeVersion:
    resume = Resume(id=uuid4(), user_id=user.id, filename="resume.pdf", original_text=text)
    db.add(resume)
    db.flush()
    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name="Original",
        content_text=text,
        content_fingerprint=compute_content_fingerprint(text),
        original_filename="resume.pdf",
        storage_path=f"/tmp/{uuid4()}.pdf",
        is_master=True,
    )
    db.add(version)
    db.flush()
    return version


def _improvement(assessment, **match):
    return next(
        item for item in assessment.result["improvements"]
        if all(item.get(k) == v for k, v in match.items())
    )


def _reject_all(assessment, exclude=()):
    return [
        {"improvement_id": item["improvement_id"], "action": "reject"}
        for item in assessment.result["improvements"]
        if item["improvement_id"] not in exclude
    ]


def _approve_bullet(
    assessment,
    text="Owned data quality checks for the feature store, cutting bad rows by 40%.",
):
    bullet = _improvement(assessment, anchor_line=WEAK_BULLET_1)
    return {
        "improvement_id": bullet["improvement_id"],
        "action": "approve",
        "truth_confirmed": True,
        "user_content": text,
    }


def test_assessment_is_persisted_and_reused(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)

    first = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    second = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)

    assert first.id == second.id
    assert fake_provider.calls == 1
    assert db.query(GeneralResumeAssessment).filter_by(resume_version_id=version.id).count() == 1
    assert first.content_fingerprint == version.content_fingerprint
    assert first.generation_status == "complete"


def test_ai_failure_changes_neither_score_nor_readiness(db, monkeypatch):
    user = make_user(db)
    ok_version = make_version(db, user)
    other_user = make_user(db)
    failed_version = make_version(db, other_user)

    monkeypatch.setattr(general_service, "create_general_resume_provider", FakeProvider)
    ok = assess_resume_version(db, user_id=user.id, resume_version_id=ok_version.id)

    monkeypatch.setattr(general_service, "create_general_resume_provider", FailingProvider)
    failed = assess_resume_version(db, user_id=other_user.id, resume_version_id=failed_version.id)

    assert failed.generation_status == "partial"
    assert failed.overall_score == ok.overall_score
    assert failed.result["components"] == ok.result["components"]
    assert [i["improvement_id"] for i in failed.result["improvements"]] == [
        i["improvement_id"] for i in ok.result["improvements"]
    ]
    assert compute_readiness(db, user_id=user.id, version=ok_version, assessment=ok)["state"] == \
        compute_readiness(db, user_id=other_user.id, version=failed_version, assessment=failed)["state"]


def test_missing_api_key_degrades_to_partial(db, monkeypatch):
    from apps.api.services.general_resume.providers import factory
    monkeypatch.setattr(factory.settings, "openai_api_key", None)
    monkeypatch.setattr(factory.settings, "ai_provider", "openai")
    user = make_user(db)
    version = make_version(db, user)

    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)

    assert assessment.generation_status == "partial"
    assert assessment.model_provider is None


def test_no_ai_call_when_nothing_to_explain(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user, STRONG_RESUME)

    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)

    assert fake_provider.calls == 0
    assert assessment.generation_status == "complete"
    readiness = compute_readiness(db, user_id=user.id, version=version, assessment=assessment)
    assert readiness["state"] == "ready"


def test_other_users_version_is_404(db, fake_provider):
    owner = make_user(db)
    intruder = make_user(db)
    version = make_version(db, owner)

    with pytest.raises(GeneralResumeServiceError) as exc:
        assess_resume_version(db, user_id=intruder.id, resume_version_id=version.id)
    assert exc.value.status_code == 404

    with pytest.raises(GeneralResumeServiceError):
        get_current_assessment(db, user_id=intruder.id, resume_version_id=version.id)


def test_get_never_computes(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)

    assert get_current_assessment(db, user_id=user.id, resume_version_id=version.id) is None
    assert fake_provider.calls == 0


def test_readiness_needs_review_until_every_improvement_is_resolved(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)

    readiness = compute_readiness(db, user_id=user.id, version=version, assessment=assessment)
    assert readiness["state"] == "needs_review"
    assert readiness["open_count"] == len(assessment.result["improvements"])


def test_rejecting_everything_records_rejections_creates_no_version_and_is_ready(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    versions_before = db.query(ResumeVersion).count()

    review = create_review(
        db, current_user=user, resume_version_id=version.id,
        assessment_id=assessment.id, decisions=_reject_all(assessment),
    )

    assert review.child_resume_version_id is None
    assert review.recheck_status == "not_required"
    assert review.rejected_count == len(assessment.result["improvements"])
    assert db.query(ResumeVersion).count() == versions_before
    readiness = compute_readiness(db, user_id=user.id, version=version, assessment=assessment)
    assert readiness["state"] == "ready"
    assert readiness["open_count"] == 0


def test_approval_creates_child_leaves_parent_untouched_and_rechecks(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    parent_text = version.content_text
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    bullet = _improvement(assessment, anchor_line=WEAK_BULLET_1)

    review = create_review(
        db, current_user=user, resume_version_id=version.id,
        assessment_id=assessment.id,
        decisions=[_approve_bullet(assessment)] + _reject_all(
            assessment, exclude={bullet["improvement_id"]}
        ),
    )

    db.refresh(version)
    child = db.get(ResumeVersion, review.child_resume_version_id)
    assert version.content_text == parent_text
    assert version.is_master is True
    assert child.parent_version_id == version.id
    assert child.source == "general_improvement"
    assert child.is_master is False
    assert child.name == "Refined 1"
    assert child.storage_path is None
    assert review.recheck_status == "complete"

    recheck = db.get(GeneralResumeAssessment, review.recheck_assessment_id)
    assert recheck.resume_version_id == child.id
    assert recheck.scoring_version == assessment.scoring_version
    assert recheck.analyzer_version == assessment.analyzer_version

    payload = serialize_review(db, user_id=user.id, review=review)
    comparison = payload["comparison"]
    assert comparison["baseline_score"] == assessment.overall_score
    assert comparison["recheck_score"] == recheck.overall_score
    assert comparison["score_delta"] == round(recheck.overall_score - assessment.overall_score, 1)
    changes = {c["improvement_id"]: c for c in comparison["changes"]}
    assert changes[bullet["improvement_id"]]["transition"] == "resolved"
    assert changes[bullet["improvement_id"]]["was_approved"] is True

    # Rejections on the parent carry forward to the unchanged issues in
    # the child, so the child is Ready.
    assert payload["resulting_readiness"]["state"] == "ready"

    # The parent points at its refined version.
    parent_readiness = compute_readiness(db, user_id=user.id, version=version, assessment=assessment)
    assert parent_readiness["state"] == "superseded"
    assert parent_readiness["refined_version_id"] == str(child.id)


def test_rejection_does_not_carry_forward_when_the_issue_changed(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    bullet = _improvement(assessment, anchor_line=WEAK_BULLET_1)

    review = create_review(
        db, current_user=user, resume_version_id=version.id,
        assessment_id=assessment.id,
        # The replacement is still weak, so the child gets a NEW issue on
        # that line - one the user has never rejected.
        decisions=[_approve_bullet(assessment, "Helped with data quality checks.")]
        + _reject_all(assessment, exclude={bullet["improvement_id"]}),
    )
    payload = serialize_review(db, user_id=user.id, review=review)

    assert payload["comparison"]["new_count"] == 1
    assert payload["resulting_readiness"]["state"] == "needs_review"
    assert payload["resulting_readiness"]["open_count"] == 1


def test_duplicate_review_never_creates_a_second_version(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    decisions = [_approve_bullet(assessment)]

    first = create_review(db, current_user=user, resume_version_id=version.id,
                          assessment_id=assessment.id, decisions=decisions)
    second = create_review(db, current_user=user, resume_version_id=version.id,
                           assessment_id=assessment.id, decisions=list(reversed(decisions)))

    assert first.id == second.id
    assert db.query(ResumeVersion).filter_by(parent_version_id=version.id).count() == 1
    assert db.query(GeneralResumeReview).filter_by(assessment_id=assessment.id).count() == 1


def test_rejected_submission_creates_nothing(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    decision = _approve_bullet(assessment)
    decision["truth_confirmed"] = False

    with pytest.raises(GeneralResumeServiceError) as exc:
        create_review(db, current_user=user, resume_version_id=version.id,
                      assessment_id=assessment.id, decisions=[decision])

    assert exc.value.code == "truth_confirmation_required"
    assert db.query(GeneralResumeReview).filter_by(assessment_id=assessment.id).count() == 0
    assert db.query(ResumeVersion).filter_by(parent_version_id=version.id).count() == 0


def test_assessment_must_belong_to_the_version(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    other = make_version(db, user, STRONG_RESUME)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)

    with pytest.raises(GeneralResumeServiceError) as exc:
        create_review(db, current_user=user, resume_version_id=other.id,
                      assessment_id=assessment.id, decisions=_reject_all(assessment))

    assert exc.value.status_code == 404


def test_failed_recheck_keeps_the_version_and_can_be_retried(db, fake_provider, monkeypatch):
    user = make_user(db)
    version = make_version(db, user)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)

    original = general_service.assess_resume_version
    calls = {"n": 0}

    def flaky(db_, *, user_id, resume_version_id):
        if resume_version_id != version.id and calls["n"] == 0:
            calls["n"] += 1
            raise RuntimeError("boom")
        return original(db_, user_id=user_id, resume_version_id=resume_version_id)

    monkeypatch.setattr(general_service, "assess_resume_version", flaky)

    review = create_review(db, current_user=user, resume_version_id=version.id,
                           assessment_id=assessment.id,
                           decisions=[_approve_bullet(assessment)])

    assert review.recheck_status == "failed"
    assert review.recheck_error == "The recheck could not be completed."
    child = db.get(ResumeVersion, review.child_resume_version_id)
    assert child is not None
    assert compute_readiness(db, user_id=user.id, version=version,
                             assessment=assessment)["state"] == "recheck_failed"

    retried = run_review_recheck(db, current_user=user, review_id=review.id)

    assert retried.recheck_status == "complete"
    assert retried.child_resume_version_id == child.id
    assert db.query(ResumeVersion).filter_by(parent_version_id=version.id).count() == 1

    # A completed recheck is never re-pointed.
    again = run_review_recheck(db, current_user=user, review_id=review.id)
    assert again.recheck_assessment_id == retried.recheck_assessment_id


def test_review_of_other_users_resource_is_404(db, fake_provider):
    owner = make_user(db)
    intruder = make_user(db)
    version = make_version(db, owner)
    assessment = assess_resume_version(db, user_id=owner.id, resume_version_id=version.id)
    review = create_review(db, current_user=owner, resume_version_id=version.id,
                           assessment_id=assessment.id, decisions=_reject_all(assessment))

    with pytest.raises(GeneralResumeServiceError) as exc:
        create_review(db, current_user=intruder, resume_version_id=version.id,
                      assessment_id=assessment.id, decisions=_reject_all(assessment))
    assert exc.value.status_code == 404

    with pytest.raises(GeneralResumeServiceError) as exc:
        run_review_recheck(db, current_user=intruder, review_id=review.id)
    assert exc.value.status_code == 404


def test_serialized_assessment_marks_dismissed_items_and_hides_anchor(db, fake_provider):
    user = make_user(db)
    version = make_version(db, user)
    assessment = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    first_id = assessment.result["improvements"][0]["improvement_id"]
    create_review(db, current_user=user, resume_version_id=version.id,
                  assessment_id=assessment.id,
                  decisions=[{"improvement_id": first_id, "action": "reject"}])

    payload = serialize_assessment(db, user_id=user.id, assessment=assessment)
    statuses = {i["improvement_id"]: i["status"] for i in payload["improvements"]}

    assert statuses[first_id] == "dismissed"
    assert list(statuses.values()).count("open") == len(statuses) - 1
    assert all("anchor_line" not in i for i in payload["improvements"])
    assert payload["readiness"]["state"] == "needs_review"
    assert payload["latest_review"]["rejected_count"] == 1


def test_assessments_are_insert_only_per_pipeline_version(db, fake_provider, monkeypatch):
    user = make_user(db)
    version = make_version(db, user)
    first = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)
    original_result = dict(first.result)

    monkeypatch.setattr(general_service, "SCORING_VERSION", "9.9")
    second = assess_resume_version(db, user_id=user.id, resume_version_id=version.id)

    db.refresh(first)
    assert second.id != first.id
    assert first.result == original_result
