"""Authenticated API tests for General Resume Intelligence (AJI-027)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import ResumeVersion
from apps.api.security import create_access_token
from apps.api.services.general_resume import service as general_service

from tests.general_resume_fixtures import WEAK_BULLET_1, WEAK_RESUME
from tests.test_general_resume_service import FakeProvider, make_user, make_version


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setattr(
        general_service, "create_general_resume_provider", FakeProvider
    )


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _assess(client, user, version):
    return client.post(
        f"/resumes/versions/{version.id}/general-assessment",
        headers=_headers(user),
    )


def test_requires_authentication(client, db):
    user = make_user(db)
    version = make_version(db, user)

    assert client.post(f"/resumes/versions/{version.id}/general-assessment").status_code == 401
    assert client.get(f"/resumes/versions/{version.id}/general-assessment").status_code == 401
    assert client.post(f"/resumes/general-reviews/{uuid4()}/recheck").status_code == 401


def test_get_before_assessment_is_404_and_does_not_compute(client, db):
    user = make_user(db)
    version = make_version(db, user)

    response = client.get(
        f"/resumes/versions/{version.id}/general-assessment", headers=_headers(user)
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "assessment_not_found"


def test_assessment_response_shape(client, db):
    user = make_user(db)
    version = make_version(db, user)

    response = _assess(client, user, version)

    assert response.status_code == 200
    body = response.json()
    assert body["resume_version_id"] == str(version.id)
    assert [c["key"] for c in body["components"]] == [
        "structure", "action_writing", "measurable_impact", "clarity", "skill_evidence",
    ]
    assert body["readiness"]["state"] == "needs_review"
    assert body["validation"]["valid"] is True
    assert all(i["status"] == "open" for i in body["improvements"])
    for forbidden in ("ats", "job_id", "threshold", "band"):
        assert forbidden not in body

    same = client.get(
        f"/resumes/versions/{version.id}/general-assessment", headers=_headers(user)
    ).json()
    assert same["id"] == body["id"]
    assert same["overall_score"] == body["overall_score"]


def test_assessment_rejects_job_input(client, db):
    user = make_user(db)
    version = make_version(db, user)

    response = client.post(
        f"/resumes/versions/{version.id}/general-assessment",
        headers=_headers(user),
        json={"job_id": str(uuid4())},
    )

    assert response.status_code == 422


def test_user_isolation(client, db):
    owner = make_user(db)
    intruder = make_user(db)
    version = make_version(db, owner)
    assessment = _assess(client, owner, version).json()

    assert _assess(client, intruder, version).status_code == 404
    get = client.get(
        f"/resumes/versions/{version.id}/general-assessment", headers=_headers(intruder)
    )
    assert get.status_code == 404
    assert "Responsible" not in get.text

    review = client.post(
        f"/resumes/versions/{version.id}/general-assessment/{assessment['id']}/review",
        headers=_headers(intruder),
        json={"decisions": [{"improvement_id": assessment["improvements"][0]["improvement_id"], "action": "reject"}]},
    )
    assert review.status_code == 404


def test_full_flow_approve_create_recheck_compare_ready(client, db):
    user = make_user(db)
    version = make_version(db, user)
    assessment = _assess(client, user, version).json()
    bullet = next(i for i in assessment["improvements"] if i["evidence"] == WEAK_BULLET_1[2:])
    decisions = [
        {
            "improvement_id": bullet["improvement_id"],
            "action": "approve",
            "truth_confirmed": True,
            "user_content": "Owned data quality checks, cutting bad rows by 40%.",
        }
    ] + [
        {"improvement_id": i["improvement_id"], "action": "reject"}
        for i in assessment["improvements"]
        if i["improvement_id"] != bullet["improvement_id"]
    ]

    response = client.post(
        f"/resumes/versions/{version.id}/general-assessment/{assessment['id']}/review",
        headers=_headers(user),
        json={"decisions": decisions},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recheck_status"] == "complete"
    assert body["child_resume_version_name"] == "Refined 1"
    assert body["comparison"]["baseline_score"] == assessment["overall_score"]
    assert body["comparison"]["resolved_count"] >= 1
    assert body["resulting_readiness"]["state"] == "ready"

    versions = client.get(
        f"/resumes/{version.resume_id}/versions", headers=_headers(user)
    ).json()
    child = next(v for v in versions if v["id"] == body["child_resume_version_id"])
    assert child["source"] == "general_improvement"
    assert child["parent_version_id"] == str(version.id)
    assert child["is_master"] is False
    assert child["has_file"] is False

    parent_view = client.get(
        f"/resumes/versions/{version.id}/general-assessment", headers=_headers(user)
    ).json()
    assert parent_view["readiness"]["state"] == "superseded"
    assert parent_view["latest_review"]["id"] == body["id"]

    child_view = client.get(
        f"/resumes/versions/{child['id']}/general-assessment", headers=_headers(user)
    ).json()
    assert child_view["readiness"]["state"] == "ready"

    # The same submission again is idempotent.
    again = client.post(
        f"/resumes/versions/{version.id}/general-assessment/{assessment['id']}/review",
        headers=_headers(user),
        json={"decisions": decisions},
    )
    assert again.json()["id"] == body["id"]
    assert db.query(ResumeVersion).filter_by(parent_version_id=version.id).count() == 1


def test_reject_all_is_ready_without_new_version(client, db):
    user = make_user(db)
    version = make_version(db, user)
    assessment = _assess(client, user, version).json()

    response = client.post(
        f"/resumes/versions/{version.id}/general-assessment/{assessment['id']}/review",
        headers=_headers(user),
        json={"decisions": [
            {"improvement_id": i["improvement_id"], "action": "reject"}
            for i in assessment["improvements"]
        ]},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["child_resume_version_id"] is None
    assert body["recheck_status"] == "not_required"
    assert body["resulting_readiness"]["state"] == "ready"


@pytest.mark.parametrize("extra", [
    {"suggestion_type": "REPHRASE_EXISTING"},
    {"applied_text": "system text"},
])
def test_client_cannot_steer_type_or_text(client, db, extra):
    user = make_user(db)
    version = make_version(db, user)
    assessment = _assess(client, user, version).json()
    decision = {
        "improvement_id": assessment["improvements"][0]["improvement_id"],
        "action": "approve",
        "user_content": "x",
        **extra,
    }

    response = client.post(
        f"/resumes/versions/{version.id}/general-assessment/{assessment['id']}/review",
        headers=_headers(user),
        json={"decisions": [decision]},
    )

    assert response.status_code == 422


def test_validation_errors_use_code_and_message(client, db):
    user = make_user(db)
    version = make_version(db, user)
    assessment = _assess(client, user, version).json()
    bullet = next(i for i in assessment["improvements"] if i["kind"] == "bullet")

    response = client.post(
        f"/resumes/versions/{version.id}/general-assessment/{assessment['id']}/review",
        headers=_headers(user),
        json={"decisions": [{
            "improvement_id": bullet["improvement_id"],
            "action": "approve",
            "user_content": "Owned checks.",
        }]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "truth_confirmation_required"
    assert response.json()["detail"]["message"]


def test_retry_recheck_endpoint_is_idempotent(client, db):
    user = make_user(db)
    version = make_version(db, user)
    assessment = _assess(client, user, version).json()
    review = client.post(
        f"/resumes/versions/{version.id}/general-assessment/{assessment['id']}/review",
        headers=_headers(user),
        json={"decisions": [
            {"improvement_id": assessment["improvements"][0]["improvement_id"], "action": "reject"}
        ]},
    ).json()

    response = client.post(
        f"/resumes/general-reviews/{review['id']}/recheck", headers=_headers(user)
    )

    assert response.status_code == 200
    assert response.json()["recheck_status"] == "not_required"
    assert client.post(
        f"/resumes/general-reviews/{uuid4()}/recheck", headers=_headers(user)
    ).status_code == 404


def test_public_jobs_listing_is_unaffected(client, db):
    user = make_user(db)
    version = make_version(db, user)
    _assess(client, user, version)

    response = client.get("/jobs")

    assert response.status_code == 200
    assert "overall_score" not in response.text
    assert "readiness" not in response.text
