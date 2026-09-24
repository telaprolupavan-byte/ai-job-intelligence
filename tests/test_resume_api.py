from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.dependencies import get_current_user
from apps.api.database import get_db
from apps.api.main import app
from apps.api.models import User
from apps.api.routers import resumes as resumes_router
from apps.api.services.resume_ai.service import ResumeAIServiceError


client = TestClient(app)


def _override_dependencies(user_id):
    user = User(id=user_id, email="user@example.com")

    def override_user():
        return user

    def override_db():
        yield SimpleNamespace()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return user


def _clear_overrides():
    app.dependency_overrides.clear()


def test_ai_analysis_post_requires_authentication():
    response = client.post(f"/resumes/versions/{uuid4()}/ai-analysis")

    assert response.status_code == 401


def test_ai_analysis_post_delegates_with_current_user(monkeypatch):
    user_id = uuid4()
    user = _override_dependencies(user_id)
    resume_version_id = uuid4()
    calls = {}

    def fake_analyze(**kwargs):
        calls.update(kwargs)
        return {"resume_version_id": str(resume_version_id)}

    monkeypatch.setattr(resumes_router, "analyze_resume_version", fake_analyze)

    try:
        response = client.post(
            f"/resumes/versions/{resume_version_id}/ai-analysis"
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert calls["user_id"] == user.id
    assert calls["resume_version_id"] == resume_version_id


def test_ai_analysis_post_rejects_service_ownership_failure(monkeypatch):
    _override_dependencies(uuid4())
    resume_version_id = uuid4()

    def fake_analyze(**kwargs):
        raise ResumeAIServiceError(
            "Resume version not found.",
            status_code=404,
        )

    monkeypatch.setattr(resumes_router, "analyze_resume_version", fake_analyze)

    try:
        response = client.post(
            f"/resumes/versions/{resume_version_id}/ai-analysis"
        )
    finally:
        _clear_overrides()

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume version not found."


def test_ai_analysis_post_maps_service_failure_to_unavailable(monkeypatch):
    _override_dependencies(uuid4())
    resume_version_id = uuid4()

    def fake_analyze(**kwargs):
        raise ResumeAIServiceError(
            "Unable to generate a valid resume AI analysis.",
            status_code=503,
        )

    monkeypatch.setattr(resumes_router, "analyze_resume_version", fake_analyze)

    try:
        response = client.post(
            f"/resumes/versions/{resume_version_id}/ai-analysis"
        )
    finally:
        _clear_overrides()

    assert response.status_code == 503


def test_ai_analysis_get_returns_current_users_analysis():
    user_id = uuid4()
    _override_dependencies(user_id)
    analysis = SimpleNamespace(
        id=uuid4(),
        resume_version_id=uuid4(),
        analysis_version="1.0",
        analyzer_version="1.0",
        model_provider="fake",
        model_name="fake-model",
        prompt_version="1.0",
        analysis_result={"findings": []},
        created_at="2026-09-16T00:00:00",
    )

    class AnalysisQuery:
        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def first(self):
            return analysis

    class FakeDB:
        def query(self, *args):
            return AnalysisQuery()

    def override_db():
        yield FakeDB()

    app.dependency_overrides[get_db] = override_db

    try:
        response = client.get(
            f"/resumes/versions/{analysis.resume_version_id}/ai-analysis"
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["model_provider"] == "fake"
    assert response.json()["analysis_result"] == {"findings": []}


def test_ai_analysis_get_is_scoped_to_current_user():
    user_id = uuid4()
    _override_dependencies(user_id)

    class EmptyQuery:
        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def first(self):
            return None

    class FakeDB:
        def query(self, *args):
            return EmptyQuery()

    def override_db():
        yield FakeDB()

    app.dependency_overrides[get_db] = override_db

    try:
        response = client.get(
            f"/resumes/versions/{uuid4()}/ai-analysis"
        )
    finally:
        _clear_overrides()

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume AI analysis not found."


def test_version_listing_reports_general_improvement_source(db):
    """AJI-027: a General Resume Intelligence version is listed with its
    own source, its lineage, no stored file, and is never master."""
    from apps.api.models import Resume, ResumeVersion
    from apps.api.services.resume_fingerprint import compute_content_fingerprint

    user = User(
        id=uuid4(),
        email=f"resume-api-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    resume = Resume(id=uuid4(), user_id=user.id, filename="r.pdf")
    db.add(resume)
    db.flush()
    parent = ResumeVersion(
        id=uuid4(), resume_id=resume.id, name="Original", content_text="a",
        content_fingerprint=compute_content_fingerprint("a"),
        original_filename="r.pdf", storage_path="/tmp/r.pdf", is_master=True,
    )
    db.add(parent)
    db.flush()
    child = ResumeVersion(
        id=uuid4(), resume_id=resume.id, name="Refined 1", content_text="b",
        content_fingerprint=compute_content_fingerprint("b"),
        original_filename="r.pdf", storage_path=None,
        parent_version_id=parent.id, source="general_improvement",
        is_master=False,
    )
    db.add(child)
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = TestClient(app).get(f"/resumes/{resume.id}/versions")
    finally:
        _clear_overrides()

    listed = {item["id"]: item for item in response.json()}
    assert response.status_code == 200
    assert listed[str(child.id)]["source"] == "general_improvement"
    assert listed[str(child.id)]["parent_version_id"] == str(parent.id)
    assert listed[str(child.id)]["has_file"] is False
    assert listed[str(child.id)]["is_master"] is False
