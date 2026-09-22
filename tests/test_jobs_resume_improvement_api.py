"""Authenticated API tests for Resume Improvement Approval & Recheck
(AJI-021): GET/POST /jobs/{job_id}/resume-improvement and
POST /jobs/{job_id}/resume-improvement/{id}/recheck.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import (
    Company,
    Job,
    Preference,
    Profile,
    RequirementIntelligence,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.security import create_access_token
from apps.api.services.gap_analysis import service as gap_analysis_service
from apps.api.services.job_intelligence import service as job_intelligence_service
from apps.api.services.requirement_intelligence.contracts import (
    RequirementIntelligenceResult,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint


RESUME_TEXT = """Jane Doe
jane@example.com

PROFESSIONAL EXPERIENCE
- Built billing services at Acme.

SKILLS
SQL
"""


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


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fake_ai_providers(monkeypatch):
    monkeypatch.setattr(
        job_intelligence_service,
        "create_job_intelligence_provider",
        lambda: FakeJobIntelligenceProvider(),
    )
    monkeypatch.setattr(
        gap_analysis_service,
        "create_gap_analysis_provider",
        lambda: FakeGapAnalysisProvider(),
    )


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"improvement-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id, years_experience=5.0))
    db.add(Preference(id=uuid4(), user_id=user.id))
    db.flush()

    return user


def _auth_headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _make_resume_version(db, *, user: User) -> ResumeVersion:
    resume = Resume(
        id=uuid4(),
        user_id=user.id,
        filename="resume.pdf",
        original_text=RESUME_TEXT,
    )
    db.add(resume)
    db.flush()

    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name="Original",
        content_text=RESUME_TEXT,
        content_fingerprint=compute_content_fingerprint(RESUME_TEXT),
        original_filename="resume.pdf",
        storage_path=f"/tmp/{uuid4()}.pdf",
        is_master=True,
    )
    db.add(version)
    db.flush()

    return version


def _make_job(db) -> Job:
    company = Company(
        id=uuid4(),
        name="Improvement API Test Co",
        normalized_name="improvement api test co",
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
        description="Kubernetes required.",
        requirements="Kubernetes required.",
        source="test",
        source_url=f"https://example.com/jobs/{uuid4()}",
    )
    db.add(job)
    db.flush()

    return job


def _make_requirement_intelligence(db, *, job: Job, user: User) -> None:
    payload = {
        "analysis_version": "1.0",
        "analyzer_version": "1.0",
        "prompt_version": "1.0",
        "model_provider": None,
        "model_name": None,
        "extraction_status": "complete",
        "source_id": str(job.id),
        "identity": {"original_title": job.title},
        "domain": {},
        "requirements": [
            {
                "id": "req-skill-kubernetes",
                "requirement_type": "skill",
                "importance": "required",
                "statement": "Kubernetes (required)",
                "canonical_terms": ["kubernetes"],
                "raw_text": "Kubernetes required.",
                "confidence": "high",
            }
        ],
        "relationships": [],
        "screening_constraints": [],
        "quality": {},
        "security": {},
    }
    validated = RequirementIntelligenceResult.model_validate(payload)

    db.add(
        RequirementIntelligence(
            id=uuid4(),
            user_id=user.id,
            job_id=job.id,
            content_fingerprint=f"fingerprint-{uuid4()}",
            raw_jd_snapshot={"title": job.title},
            analysis_version="1.0",
            analyzer_version="1.0",
            prompt_version="1.0",
            extraction_status="complete",
            structured_intelligence=validated.model_dump(mode="json"),
        )
    )
    db.flush()


@pytest.fixture
def scenario(db):
    """A user with a resume, a job, and a stored Gap Analysis - i.e. the
    Analyze -> Review stages already done over HTTP."""
    user = _make_user(db)
    job = _make_job(db)
    version = _make_resume_version(db, user=user)
    _make_requirement_intelligence(db, job=job, user=user)

    return {"user": user, "job": job, "version": version}


def _create_gap_analysis(client, scenario) -> dict:
    response = client.post(
        f"/jobs/{scenario['job'].id}/gap-analysis",
        headers=_auth_headers(scenario["user"]),
    )
    assert response.status_code == 200
    return response.json()


def _approval_body(gap_analysis: dict, **overrides) -> dict:
    decision = {
        "requirement_id": "req-skill-kubernetes",
        "action": "approve",
        "truth_confirmed": True,
        "user_content": "Operated Kubernetes clusters in production at Acme.",
    }
    decision.update(overrides)

    return {
        "gap_analysis_id": gap_analysis["id"],
        "decisions": [decision],
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_get_resume_improvement_requires_authentication(client, scenario):
    response = client.get(f"/jobs/{scenario['job'].id}/resume-improvement")
    assert response.status_code == 401


def test_post_resume_improvement_requires_authentication(client, scenario):
    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        json={"gap_analysis_id": str(uuid4()), "decisions": []},
    )
    assert response.status_code == 401


def test_recheck_requires_authentication(client, scenario):
    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement/{uuid4()}/recheck"
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------

def test_get_returns_404_before_anything_is_approved(client, scenario):
    response = client.get(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
    )
    assert response.status_code == 404


def test_post_with_an_unknown_job_is_404(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    response = client.post(
        f"/jobs/{uuid4()}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    )
    assert response.status_code == 404


def test_post_with_a_malformed_gap_analysis_id_is_404(client, scenario):
    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json={"gap_analysis_id": "not-a-uuid", "decisions": [
            {"requirement_id": "req-skill-kubernetes", "action": "skip"}
        ]},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Golden path over HTTP: Approve -> new version -> recheck -> compare
# ---------------------------------------------------------------------------

def test_the_full_approve_create_recheck_compare_flow(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    assert gap_analysis["gaps"], "fixture should produce a real gap"

    # Step 1: approve -> create the version. This does NOT recheck.
    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    )

    assert response.status_code == 200
    created = response.json()

    assert created["parent_resume_version_id"] == str(scenario["version"].id)
    assert created["child_resume_version_id"] != str(scenario["version"].id)
    assert created["child_resume_version_name"] == "Improved 1"
    assert created["parent_resume_version_name"] == "Original"
    assert created["approved_count"] == 1
    assert created["recheck_status"] == "pending"
    assert created["recheck_ats_alignment_id"] is None
    assert created["comparison"] is None

    # Step 2: "Run recheck" — an explicit, separate action.
    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement/{created['id']}/recheck",
        headers=_auth_headers(scenario["user"]),
    )
    assert response.status_code == 200
    body = response.json()

    assert body["id"] == created["id"]
    assert body["child_resume_version_id"] == created["child_resume_version_id"]
    assert body["recheck_status"] == "complete"

    comparison = body["comparison"]
    assert comparison["baseline_score"] < comparison["recheck_score"]

    transition = next(
        item
        for item in comparison["transitions"]
        if item["requirement_id"] == "req-skill-kubernetes"
    )
    assert transition["before_status"] == "missing"
    assert transition["after_status"] == "matched"

    # The decision record keeps the user's own text and the confirmation.
    decision = body["decisions"][0]
    assert decision["truth_confirmed"] is True
    assert decision["content_source"] == "user"
    assert (
        decision["applied_text"]
        == "Operated Kubernetes clusters in production at Acme."
    )


def test_get_returns_the_stored_record_after_approval(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    response = client.get(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_the_new_version_appears_in_the_resume_version_list_with_lineage(
    client, scenario
):
    gap_analysis = _create_gap_analysis(client, scenario)

    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    versions = client.get(
        f"/resumes/{scenario['version'].resume_id}/versions",
        headers=_auth_headers(scenario["user"]),
    ).json()

    by_id = {version["id"]: version for version in versions}

    child = by_id[created["child_resume_version_id"]]
    assert child["parent_version_id"] == str(scenario["version"].id)
    assert child["source"] == "improvement"
    assert child["has_file"] is False
    assert child["is_master"] is False

    parent = by_id[str(scenario["version"].id)]
    assert parent["parent_version_id"] is None
    assert parent["source"] == "upload"
    assert parent["has_file"] is True
    assert parent["is_master"] is True


def test_downloading_a_generated_version_404s_rather_than_serving_the_parents_file(
    client, scenario
):
    gap_analysis = _create_gap_analysis(client, scenario)

    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    response = client.get(
        f"/resumes/versions/{created['child_resume_version_id']}/file",
        headers=_auth_headers(scenario["user"]),
    )

    assert response.status_code == 404
    assert "no uploaded file" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Approval rules over HTTP
# ---------------------------------------------------------------------------

def test_an_empty_decision_list_is_rejected_by_the_request_schema(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json={"gap_analysis_id": gap_analysis["id"], "decisions": []},
    )

    assert response.status_code == 422


def test_skipping_everything_is_rejected_with_a_no_approvals_code(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json={
            "gap_analysis_id": gap_analysis["id"],
            "decisions": [
                {"requirement_id": "req-skill-kubernetes", "action": "skip"}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_approvals"


def test_an_unconfirmed_add_if_true_approval_is_rejected(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis, truth_confirmed=False),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "truth_confirmation_required"


def test_a_client_supplied_suggestion_type_is_rejected_outright(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    body = _approval_body(gap_analysis, truth_confirmed=False)
    body["decisions"][0]["suggestion_type"] = "REPHRASE_EXISTING"

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=body,
    )

    # The request model forbids extra fields, so a client cannot even
    # attempt to relabel a gap to escape the truth confirmation.
    assert response.status_code == 422


def test_a_client_supplied_applied_text_is_rejected_outright(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    body = _approval_body(gap_analysis)
    body["decisions"][0]["applied_text"] = "NERO says I know Kubernetes."

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=body,
    )

    assert response.status_code == 422


def test_approving_without_content_is_rejected(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis, user_content="   "),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "content_required"


def test_approving_an_invented_requirement_is_rejected(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis, requirement_id="invented-requirement"),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unknown_requirement"


def test_oversized_user_content_is_rejected_by_the_request_schema(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis, user_content="x" * 5000),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Idempotency over HTTP
# ---------------------------------------------------------------------------

def test_posting_the_same_approvals_twice_returns_the_same_record(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    body = _approval_body(gap_analysis)

    first = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=body,
    ).json()
    second = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=body,
    ).json()

    assert first["id"] == second["id"]
    assert (
        first["child_resume_version_id"] == second["child_resume_version_id"]
    )

    versions = client.get(
        f"/resumes/{scenario['version'].resume_id}/versions",
        headers=_auth_headers(scenario["user"]),
    ).json()
    assert len(versions) == 2


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------

def test_another_user_cannot_apply_someone_elses_gap_analysis(client, db, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    intruder = _make_user(db)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(intruder),
        json=_approval_body(gap_analysis),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "gap_analysis_not_found"


def test_another_user_never_sees_the_record_or_its_resume_content(
    client, db, scenario
):
    gap_analysis = _create_gap_analysis(client, scenario)
    client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    )

    intruder = _make_user(db)

    response = client.get(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(intruder),
    )

    assert response.status_code == 404
    assert "Operated Kubernetes clusters" not in response.text


def test_another_user_cannot_read_the_generated_version(client, db, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    intruder = _make_user(db)

    response = client.get(
        f"/resumes/{scenario['version'].resume_id}/versions",
        headers=_auth_headers(intruder),
    )
    assert response.status_code == 404

    file_response = client.get(
        f"/resumes/versions/{created['child_resume_version_id']}/file",
        headers=_auth_headers(intruder),
    )
    assert file_response.status_code == 404
    assert "Resume version not found." in file_response.json()["detail"]


# ---------------------------------------------------------------------------
# Recheck retry endpoint
# ---------------------------------------------------------------------------

def test_recheck_of_an_unknown_record_is_404(client, scenario):
    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement/{uuid4()}/recheck",
        headers=_auth_headers(scenario["user"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "improvement_not_found"


def test_recheck_of_a_completed_record_returns_it_unchanged(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    first = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement/{created['id']}/recheck",
        headers=_auth_headers(scenario["user"]),
    ).json()
    assert first["recheck_status"] == "complete"

    # Running it again never re-points a completed recheck.
    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement/{created['id']}/recheck",
        headers=_auth_headers(scenario["user"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["recheck_ats_alignment_id"] == first["recheck_ats_alignment_id"]


def test_another_user_cannot_retry_a_recheck(client, db, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    intruder = _make_user(db)

    response = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement/{created['id']}/recheck",
        headers=_auth_headers(intruder),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# No leakage into the public surface
# ---------------------------------------------------------------------------

def test_the_public_jobs_listing_never_includes_improvement_data(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    )

    response = client.get("/jobs")

    assert response.status_code == 200
    assert "resume_improvement" not in response.text
    assert "Operated Kubernetes clusters" not in response.text


def test_existing_ats_and_gap_analysis_endpoints_still_work(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)
    client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    )

    ats = client.get(
        f"/jobs/{scenario['job'].id}/ats",
        headers=_auth_headers(scenario["user"]),
    )
    assert ats.status_code == 200

    gaps = client.get(
        f"/jobs/{scenario['job'].id}/gap-analysis",
        headers=_auth_headers(scenario["user"]),
    )
    assert gaps.status_code == 200
    # The stored Gap Analysis is unchanged by having been acted on.
    assert gaps.json()["id"] == gap_analysis["id"]


# ---------------------------------------------------------------------------
# "Run recheck" is a separate, explicit action over HTTP
# ---------------------------------------------------------------------------

def test_creating_a_version_over_http_does_not_recheck(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    assert created["recheck_status"] == "pending"
    assert created["recheck_ats_alignment_id"] is None
    assert created["comparison"] is None

    # Reading it back still shows a pending, fully-created version.
    fetched = client.get(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
    ).json()
    assert fetched["id"] == created["id"]
    assert fetched["recheck_status"] == "pending"
    assert (
        fetched["child_resume_version_id"] == created["child_resume_version_id"]
    )


def test_a_pending_version_is_still_listed_in_the_resume_library(
    client, scenario
):
    gap_analysis = _create_gap_analysis(client, scenario)

    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    versions = client.get(
        f"/resumes/{scenario['version'].resume_id}/versions",
        headers=_auth_headers(scenario["user"]),
    ).json()

    by_id = {version["id"]: version for version in versions}
    assert created["child_resume_version_id"] in by_id
    assert by_id[created["child_resume_version_id"]]["source"] == "improvement"
    # The original is untouched whether or not the recheck ever runs.
    assert by_id[str(scenario["version"].id)]["is_master"] is True


def test_the_response_carries_both_real_version_names(client, scenario):
    gap_analysis = _create_gap_analysis(client, scenario)

    created = client.post(
        f"/jobs/{scenario['job'].id}/resume-improvement",
        headers=_auth_headers(scenario["user"]),
        json=_approval_body(gap_analysis),
    ).json()

    assert created["parent_resume_version_name"] == "Original"
    assert created["child_resume_version_name"] == "Improved 1"
