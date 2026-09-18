"""Tests for multi-resume, version-aware resume management.

Covers: multiple resumes coexisting, exact-duplicate detection,
content-based revisioning, collision-safe/authenticated file storage,
version scoping, AI analysis association per version, AI analysis
caching, and master-version preservation.
"""
from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Resume, ResumeAIAnalysis, ResumeVersion, User
from apps.api.security import create_access_token
from apps.api.services.resume_ai.interpreter import (
    ANALYSIS_VERSION,
    PROMPT_VERSION,
)
from apps.api.services.resume_ai.service import ANALYZER_VERSION
from apps.api.services.resume_service import resolve_stored_file, RESUME_UPLOAD_DIR


RESUME_TEXT_AI = """Jordan Rivera
AI/ML Resume

SUMMARY
AI and machine learning engineer focused on building production grade
natural language processing and computer vision systems for enterprise
customers.

EXPERIENCE
- Built and deployed deep learning models using Python and PyTorch for a
  document classification pipeline
- Reduced model inference latency by 30 percent through quantization and
  caching improvements
- Designed a retrieval augmented generation system using LangChain and a
  vector database to answer customer support questions
- Led a cross functional team of four engineers to ship a computer vision
  feature for defect detection

SKILLS
Python, PyTorch, TensorFlow, LangChain, Docker, Kubernetes, AWS, SQL,
Machine Learning, Deep Learning, Generative AI, NLP

EDUCATION
B.S. Computer Science, State University

PROJECTS
Built an open source chatbot using large language models and retrieval
augmented generation that answers questions from a document corpus with
measurable accuracy improvements over a keyword search baseline.
"""

RESUME_TEXT_AI_REVISED = RESUME_TEXT_AI + (
    "\nADDITIONAL EXPERIENCE\n"
    "- Migrated the training pipeline to a distributed Spark cluster, "
    "cutting training time by 40 percent.\n"
)

RESUME_TEXT_DATACENTER = """Jordan Rivera
Data Center Resume

SUMMARY
Data center operations engineer with experience managing large scale
infrastructure, network reliability, and hardware lifecycle management
for enterprise data centers.

EXPERIENCE
- Managed rack level hardware deployments across multiple data center
  facilities
- Reduced unplanned downtime by 25 percent through improved monitoring
  and alerting practices
- Coordinated with vendors to plan capacity upgrades for power and
  cooling systems
- Automated routine maintenance tasks using Python scripts and internal
  tooling

SKILLS
Linux, Networking, Python, Bash, Data Center Operations, Capacity
Planning, Monitoring, Hardware Lifecycle Management

EDUCATION
B.S. Information Technology, State University

PROJECTS
Built an internal dashboard using Python that tracks hardware inventory
and lifecycle status across multiple data center facilities, reducing
manual audit time significantly.
"""


def make_docx_bytes(text: str) -> bytes:
    document = Document()

    for line in text.split("\n"):
        document.add_paragraph(line)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument"
    ".wordprocessingml.document"
)


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_user(db, *, email: str | None = None) -> User:
    user = User(
        id=uuid4(),
        email=email or f"resume-test-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def auth_headers_for(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user(db):
    return make_user(db)


@pytest.fixture
def headers(user):
    return auth_headers_for(user)


@pytest.fixture
def other_user(db):
    return make_user(db)


@pytest.fixture
def other_headers(other_user):
    return auth_headers_for(other_user)


def upload(
    client: TestClient,
    headers: dict,
    text: str,
    *,
    filename: str = "resume.docx",
    resume_id: str | None = None,
    version_name: str | None = None,
):
    data = {}
    if resume_id is not None:
        data["resume_id"] = resume_id
    if version_name is not None:
        data["version_name"] = version_name

    files = {
        "file": (filename, make_docx_bytes(text), DOCX_MEDIA_TYPE),
    }

    return client.post(
        "/resumes/upload",
        headers=headers,
        files=files,
        data=data,
    )


# =========================
# Multiple resumes
# =========================


def test_multiple_distinct_resumes_coexist(client, headers):
    resp_a = upload(client, headers, RESUME_TEXT_AI, filename="ai_resume.docx")
    assert resp_a.status_code == 201
    resp_b = upload(
        client, headers, RESUME_TEXT_DATACENTER, filename="dc_resume.docx"
    )
    assert resp_b.status_code == 201

    assert resp_a.json()["id"] != resp_b.json()["id"]

    listing = client.get("/resumes", headers=headers)
    assert listing.status_code == 200
    resume_ids = {item["id"] for item in listing.json()}

    assert resp_a.json()["id"] in resume_ids
    assert resp_b.json()["id"] in resume_ids
    assert len(listing.json()) == 2


def test_second_upload_does_not_overwrite_first(client, headers):
    resp_a = upload(client, headers, RESUME_TEXT_AI, filename="ai_resume.docx")
    upload(client, headers, RESUME_TEXT_DATACENTER, filename="dc_resume.docx")

    detail = client.get(f"/resumes/{resp_a.json()['id']}", headers=headers)
    assert detail.status_code == 200
    assert "AI and machine learning engineer" in detail.json()["original_text"]


# =========================
# Duplicate detection
# =========================


def test_exact_duplicate_upload_does_not_create_new_version(client, headers):
    first = upload(client, headers, RESUME_TEXT_AI)
    assert first.status_code == 201

    second = upload(client, headers, RESUME_TEXT_AI, filename="different_name.docx")
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["version_id"] == first.json()["version_id"]
    assert second.json()["id"] == first.json()["id"]

    versions = client.get(
        f"/resumes/{first.json()['id']}/versions", headers=headers
    )
    assert len(versions.json()) == 1


def test_exact_duplicate_does_not_create_second_resume(client, headers):
    upload(client, headers, RESUME_TEXT_AI)
    upload(client, headers, RESUME_TEXT_AI, filename="renamed.docx")

    listing = client.get("/resumes", headers=headers)
    assert len(listing.json()) == 1


def test_duplicate_is_detected_regardless_of_filename(client, headers):
    first = upload(client, headers, RESUME_TEXT_AI, filename="a.docx")
    second = upload(client, headers, RESUME_TEXT_AI, filename="completely_different_name.docx")

    assert second.json()["duplicate"] is True
    assert second.json()["version_id"] == first.json()["version_id"]


# =========================
# Revisions (new content -> new version)
# =========================


def test_changed_content_creates_new_version_of_same_resume(client, headers):
    first = upload(client, headers, RESUME_TEXT_AI)
    resume_id = first.json()["id"]

    second = upload(
        client,
        headers,
        RESUME_TEXT_AI_REVISED,
        resume_id=resume_id,
        version_name="Updated",
    )

    assert second.status_code == 201
    assert second.json()["duplicate"] is False
    assert second.json()["id"] == resume_id
    assert second.json()["version_id"] != first.json()["version_id"]

    versions = client.get(f"/resumes/{resume_id}/versions", headers=headers)
    assert len(versions.json()) == 2

    listing = client.get("/resumes", headers=headers)
    assert len(listing.json()) == 1


def test_old_version_remains_accessible_after_revision(client, headers):
    first = upload(client, headers, RESUME_TEXT_AI)
    resume_id = first.json()["id"]

    upload(
        client,
        headers,
        RESUME_TEXT_AI_REVISED,
        resume_id=resume_id,
        version_name="Updated",
    )

    old_file = client.get(
        f"/resumes/versions/{first.json()['version_id']}/file",
        headers=headers,
    )
    assert old_file.status_code == 200
    assert old_file.content == make_docx_bytes(RESUME_TEXT_AI)


# =========================
# Files: view/download, auth, ownership, 404s
# =========================


def test_owner_can_download_their_resume_file(client, headers):
    result = upload(client, headers, RESUME_TEXT_AI, filename="my_resume.docx")

    response = client.get(
        f"/resumes/versions/{result.json()['version_id']}/file",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.content == make_docx_bytes(RESUME_TEXT_AI)
    assert "my_resume.docx" in response.headers.get("content-disposition", "")


def test_unauthenticated_user_cannot_access_resume_file(client, headers):
    result = upload(client, headers, RESUME_TEXT_AI)

    response = client.get(
        f"/resumes/versions/{result.json()['version_id']}/file",
    )

    assert response.status_code == 401


def test_other_user_cannot_access_resume_file(client, headers, other_headers):
    result = upload(client, headers, RESUME_TEXT_AI)

    response = client.get(
        f"/resumes/versions/{result.json()['version_id']}/file",
        headers=other_headers,
    )

    assert response.status_code == 404


def test_other_user_cannot_see_resume_in_listing(client, headers, other_headers):
    upload(client, headers, RESUME_TEXT_AI)

    listing = client.get("/resumes", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []


def test_other_user_cannot_access_resume_detail(client, headers, other_headers):
    result = upload(client, headers, RESUME_TEXT_AI)

    response = client.get(
        f"/resumes/{result.json()['id']}",
        headers=other_headers,
    )
    assert response.status_code == 404


def test_missing_resume_version_file_returns_404(client, headers):
    response = client.get(
        f"/resumes/versions/{uuid4()}/file",
        headers=headers,
    )
    assert response.status_code == 404


def test_missing_resume_returns_404(client, headers):
    response = client.get(f"/resumes/{uuid4()}", headers=headers)
    assert response.status_code == 404


def test_missing_physical_file_returns_404(client, headers, db):
    result = upload(client, headers, RESUME_TEXT_AI)
    version_id = result.json()["version_id"]

    version = db.query(ResumeVersion).filter(
        ResumeVersion.id == version_id
    ).first()
    stored_path = version.storage_path
    import os

    os.remove(stored_path)

    response = client.get(
        f"/resumes/versions/{version_id}/file",
        headers=headers,
    )
    assert response.status_code == 404


def test_path_traversal_is_rejected():
    with pytest.raises(Exception):
        resolve_stored_file(str(RESUME_UPLOAD_DIR / ".." / ".." / "etc" / "passwd"))


def test_uploaded_files_are_stored_at_collision_safe_paths(client, headers, db):
    result_a = upload(client, headers, RESUME_TEXT_AI, filename="resume.docx")
    result_b = upload(
        client, headers, RESUME_TEXT_DATACENTER, filename="resume.docx"
    )

    version_a = db.query(ResumeVersion).filter(
        ResumeVersion.id == result_a.json()["version_id"]
    ).first()
    version_b = db.query(ResumeVersion).filter(
        ResumeVersion.id == result_b.json()["version_id"]
    ).first()

    assert version_a.storage_path != version_b.storage_path


# =========================
# Versions belong only to their own Resume
# =========================


def test_versions_are_scoped_to_their_resume(client, headers):
    resume_a = upload(client, headers, RESUME_TEXT_AI, filename="a.docx")
    resume_b = upload(
        client, headers, RESUME_TEXT_DATACENTER, filename="b.docx"
    )

    versions_a = client.get(
        f"/resumes/{resume_a.json()['id']}/versions", headers=headers
    ).json()
    versions_b = client.get(
        f"/resumes/{resume_b.json()['id']}/versions", headers=headers
    ).json()

    version_ids_a = {v["id"] for v in versions_a}
    version_ids_b = {v["id"] for v in versions_b}

    assert version_ids_a.isdisjoint(version_ids_b)
    assert resume_a.json()["version_id"] in version_ids_a
    assert resume_b.json()["version_id"] in version_ids_b


def test_versions_list_reflects_per_version_analysis_state(
    client, headers, db, user
):
    first = upload(client, headers, RESUME_TEXT_AI)
    resume_id = first.json()["id"]
    version_1_id = first.json()["version_id"]

    second = upload(
        client,
        headers,
        RESUME_TEXT_AI_REVISED,
        resume_id=resume_id,
        version_name="Updated",
    )
    version_2_id = second.json()["version_id"]

    versions_before = {
        v["id"]: v
        for v in client.get(
            f"/resumes/{resume_id}/versions", headers=headers
        ).json()
    }
    assert versions_before[version_1_id]["has_analysis"] is False
    assert versions_before[version_2_id]["has_analysis"] is False

    analysis = ResumeAIAnalysis(
        id=uuid4(),
        user_id=user.id,
        resume_version_id=version_1_id,
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=PROMPT_VERSION,
        model_provider="test",
        model_name="test-model",
        analysis_result={"summary": {"strengths": ["x"]}},
    )
    db.add(analysis)
    db.flush()

    versions_after = {
        v["id"]: v
        for v in client.get(
            f"/resumes/{resume_id}/versions", headers=headers
        ).json()
    }
    assert versions_after[version_1_id]["has_analysis"] is True
    assert versions_after[version_2_id]["has_analysis"] is False
# =========================
# Master version preservation
# =========================


def test_first_version_of_new_resume_is_master(client, headers):
    result = upload(client, headers, RESUME_TEXT_AI)

    versions = client.get(
        f"/resumes/{result.json()['id']}/versions", headers=headers
    ).json()

    assert len(versions) == 1
    assert versions[0]["is_master"] is True


def test_uploading_second_resume_does_not_change_first_resumes_master(
    client, headers
):
    first = upload(client, headers, RESUME_TEXT_AI)
    upload(client, headers, RESUME_TEXT_DATACENTER)

    versions = client.get(
        f"/resumes/{first.json()['id']}/versions", headers=headers
    ).json()

    assert versions[0]["is_master"] is True


def test_new_version_of_existing_resume_does_not_become_master(client, headers):
    first = upload(client, headers, RESUME_TEXT_AI)
    resume_id = first.json()["id"]
    version_1_id = first.json()["version_id"]

    second = upload(
        client,
        headers,
        RESUME_TEXT_AI_REVISED,
        resume_id=resume_id,
        version_name="Updated",
    )
    version_2_id = second.json()["version_id"]

    versions = {
        v["id"]: v
        for v in client.get(
            f"/resumes/{resume_id}/versions", headers=headers
        ).json()
    }

    assert versions[version_1_id]["is_master"] is True
    assert versions[version_2_id]["is_master"] is False


# =========================
# AI analysis association
# =========================


def test_ai_analysis_is_scoped_to_exact_version(client, headers, db, user):
    first = upload(client, headers, RESUME_TEXT_AI)
    resume_id = first.json()["id"]
    version_1_id = first.json()["version_id"]

    second = upload(
        client,
        headers,
        RESUME_TEXT_AI_REVISED,
        resume_id=resume_id,
        version_name="Updated",
    )
    version_2_id = second.json()["version_id"]

    analysis_1 = ResumeAIAnalysis(
        id=uuid4(),
        user_id=user.id,
        resume_version_id=version_1_id,
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=PROMPT_VERSION,
        model_provider="test",
        model_name="test-model",
        analysis_result={"summary": {"strengths": ["v1 strength"]}},
    )
    analysis_2 = ResumeAIAnalysis(
        id=uuid4(),
        user_id=user.id,
        resume_version_id=version_2_id,
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=PROMPT_VERSION,
        model_provider="test",
        model_name="test-model",
        analysis_result={"summary": {"strengths": ["v2 strength"]}},
    )
    db.add_all([analysis_1, analysis_2])
    db.flush()

    resp_1 = client.get(
        f"/resumes/versions/{version_1_id}/ai-analysis", headers=headers
    )
    resp_2 = client.get(
        f"/resumes/versions/{version_2_id}/ai-analysis", headers=headers
    )

    assert resp_1.json()["analysis_result"]["summary"]["strengths"] == [
        "v1 strength"
    ]
    assert resp_2.json()["analysis_result"]["summary"]["strengths"] == [
        "v2 strength"
    ]


def test_ai_analysis_never_crosses_resumes(client, headers, db, user):
    resume_a = upload(client, headers, RESUME_TEXT_AI, filename="a.docx")
    resume_b = upload(
        client, headers, RESUME_TEXT_DATACENTER, filename="b.docx"
    )

    analysis_a = ResumeAIAnalysis(
        id=uuid4(),
        user_id=user.id,
        resume_version_id=resume_a.json()["version_id"],
        analysis_version=ANALYSIS_VERSION,
        analyzer_version=ANALYZER_VERSION,
        prompt_version=PROMPT_VERSION,
        model_provider="test",
        model_name="test-model",
        analysis_result={"summary": {"strengths": ["resume A"]}},
    )
    db.add(analysis_a)
    db.flush()

    resp_b = client.get(
        f"/resumes/versions/{resume_b.json()['version_id']}/ai-analysis",
        headers=headers,
    )

    assert resp_b.status_code == 404


def test_legacy_schema_analysis_is_treated_as_not_yet_analyzed(
    client, headers, db, user
):
    """A ResumeAIAnalysis row saved under an older analyzer/prompt
    pipeline (e.g. the pre-Resume-Intelligence flat schema) has a
    different, incompatible shape than what the current API contract and
    frontend expect. Serving it as-is previously crashed the resume page
    with "Cannot read properties of undefined (reading 'strengths')"
    because the old payload has no `review` key. It must instead be
    treated the same as "not yet analyzed" so the frontend falls back to
    its existing 404 handling instead of crashing.
    """
    result = upload(client, headers, RESUME_TEXT_AI)
    resume_id = result.json()["id"]
    version_id = result.json()["version_id"]

    legacy_analysis = ResumeAIAnalysis(
        id=uuid4(),
        user_id=user.id,
        resume_version_id=version_id,
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        model_provider="test",
        model_name="test-model",
        # The old flat schema this app used before the "Resume
        # Intelligence" restructure - no `review`/`decoding`/
        # `position_identification` keys at all.
        analysis_result={
            "profile": "Some profile text",
            "positioning": {},
            "sections": [],
            "skills": [],
            "experience": [],
            "technical_depth": {},
            "structure": {},
            "findings": [],
            "summary": "Some summary",
        },
    )
    db.add(legacy_analysis)
    db.flush()

    get_resp = client.get(
        f"/resumes/versions/{version_id}/ai-analysis", headers=headers
    )
    assert get_resp.status_code == 404

    versions = {
        v["id"]: v
        for v in client.get(
            f"/resumes/{resume_id}/versions", headers=headers
        ).json()
    }
    assert versions[version_id]["has_analysis"] is False
