from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.api.models import ResumeAIAnalysis
from apps.api.services.resume_ai import service


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self):
        self.resume_text = None
        self.deterministic_analysis = None

    def generate_structured_analysis(
        self,
        *,
        resume_text: str,
        deterministic_analysis: dict,
    ) -> dict:
        self.resume_text = resume_text
        self.deterministic_analysis = deterministic_analysis

        return {
            "profile": {
                "name": "John Doe",
            },
            "positioning": {
                "apparent_target_role": "AI/ML Engineer",
                "apparent_specialization": "Machine Learning",
                "apparent_seniority": "Mid-level",
                "positioning_strengths": ["Technical focus"],
                "positioning_risks": [],
            },
            "sections": {},
            "skills": {
                "demonstrated": ["python"],
                "skills_only": [],
                "weakly_supported": [],
            },
            "experience": {
                "bullet_count": 2,
                "achievement_count": 1,
                "responsibility_count": 1,
                "quantified_bullets": 1,
                "findings": [],
            },
            "technical_depth": {
                "programming": ["python"],
                "machine_learning": ["machine learning"],
                "deep_learning": [],
                "generative_ai": [],
                "cloud": [],
                "mlops": [],
            },
            "structure": {
                "findings": [],
            },
            "findings": [],
            "summary": {
                "strengths": ["Clear technical focus"],
                "top_priorities": ["Add measurable outcomes"],
            },
        }


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class FakeDB:
    def __init__(self, resume_version, cached_analysis=None):
        self.resume_version = resume_version
        self.cached_analysis = cached_analysis
        self.added = []
        self.committed = False
        self.refreshed = []

    def query(self, model, *args, **kwargs):
        if model is ResumeAIAnalysis:
            return FakeQuery(self.cached_analysis)
        return FakeQuery(self.resume_version)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True

    def refresh(self, item):
        self.refreshed.append(item)


def make_resume_version(text: str):
    resume = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
    )

    return SimpleNamespace(
        id=uuid4(),
        resume=resume,
        content_text=text,
    )


def test_analyze_resume_version_returns_validated_result(monkeypatch):
    resume_version = make_resume_version(
        """
        John Doe
        AI/ML Engineer
        john@example.com

        EXPERIENCE
        - Built machine learning models using Python
        - Improved inference performance by 20%

        SKILLS
        Python
        Machine Learning
        """
    )

    db = FakeDB(resume_version)
    provider = FakeProvider()

    monkeypatch.setattr(
        service,
        "create_resume_ai_provider",
        lambda: provider,
    )

    result = service.analyze_resume_version(
        db=db,
        user_id=resume_version.resume.user_id,
        resume_version_id=resume_version.id,
    )

    assert result.analysis_version == "1.0"
    assert result.resume_version_id == str(resume_version.id)
    assert result.positioning.apparent_target_role == "AI/ML Engineer"
    assert len(result.findings) == 0


def test_analyze_resume_version_passes_deterministic_analysis_to_provider(
    monkeypatch,
):
    resume_version = make_resume_version(
        """
        John Doe
        EXPERIENCE
        - Built Python applications
        - Improved performance by 20%

        SKILLS
        Python
        """
    )

    db = FakeDB(resume_version)
    provider = FakeProvider()

    monkeypatch.setattr(
        service,
        "create_resume_ai_provider",
        lambda: provider,
    )

    service.analyze_resume_version(
        db=db,
        user_id=resume_version.resume.user_id,
        resume_version_id=resume_version.id,
    )

    assert provider.resume_text == resume_version.content_text.strip()
    assert provider.deterministic_analysis is not None
    assert provider.deterministic_analysis["word_count"] > 0
    assert "skills" in provider.deterministic_analysis
    assert "skill_evidence" in provider.deterministic_analysis
    assert "technical_signals" in provider.deterministic_analysis
    assert "project_signals" in provider.deterministic_analysis
    assert "career_signals" in provider.deterministic_analysis


def test_analyze_resume_version_persists_analysis(monkeypatch):
    resume_version = make_resume_version(
        """
        John Doe
        EXPERIENCE
        - Built Python applications
        - Improved performance by 20%

        SKILLS
        Python
        """
    )

    db = FakeDB(resume_version)
    provider = FakeProvider()

    monkeypatch.setattr(
        service,
        "create_resume_ai_provider",
        lambda: provider,
    )

    result = service.analyze_resume_version(
        db=db,
        user_id=resume_version.resume.user_id,
        resume_version_id=resume_version.id,
    )

    assert len(db.added) == 1

    record = db.added[0]

    assert record.user_id == resume_version.resume.user_id
    assert record.resume_version_id == resume_version.id
    assert record.analysis_version == "1.0"
    assert record.analyzer_version == "1.0"
    assert record.model_provider == "fake"
    assert record.model_name == "fake-model"
    assert record.prompt_version == "1.0"
    assert record.analysis_result["resume_version_id"] == str(
        resume_version.id
    )
    assert record.analysis_result["summary"] == result.summary.model_dump()

    assert db.committed is True
    assert db.refreshed == [record]


def test_analyze_resume_version_rejects_missing_resume():
    db = FakeDB(None)

    with pytest.raises(
        service.ResumeAIServiceError,
        match="Resume version not found",
    ):
        service.analyze_resume_version(
            db=db,
            user_id=uuid4(),
            resume_version_id=uuid4(),
        )


def test_analyze_resume_version_rejects_empty_resume():
    resume_version = make_resume_version("   ")

    db = FakeDB(resume_version)

    with pytest.raises(
        service.ResumeAIServiceError,
        match="no readable text",
    ):
        service.analyze_resume_version(
            db=db,
            user_id=resume_version.resume.user_id,
            resume_version_id=resume_version.id,
        )

    assert db.added == []
    assert db.committed is False


def test_analyze_resume_version_does_not_modify_resume(
    monkeypatch,
):
    original_text = """
        John Doe
        EXPERIENCE
        - Built Python applications

        SKILLS
        Python
    """

    resume_version = make_resume_version(original_text)

    db = FakeDB(resume_version)
    provider = FakeProvider()

    monkeypatch.setattr(
        service,
        "create_resume_ai_provider",
        lambda: provider,
    )

    service.analyze_resume_version(
        db=db,
        user_id=resume_version.resume.user_id,
        resume_version_id=resume_version.id,
    )

    assert resume_version.content_text == original_text


def test_analyze_resume_version_reuses_cached_analysis(monkeypatch):
    resume_version = make_resume_version(
        """
        John Doe
        EXPERIENCE
        - Built Python applications
        - Improved performance by 20%

        SKILLS
        Python
        """
    )

    cached_result = {
        "analysis_version": service.ANALYSIS_VERSION,
        "resume_version_id": str(resume_version.id),
        "profile": {"name": "John Doe"},
        "positioning": {
            "apparent_target_role": "AI/ML Engineer",
            "positioning_strengths": [],
            "positioning_risks": [],
        },
        "sections": {},
        "skills": {
            "demonstrated": ["python"],
            "skills_only": [],
            "weakly_supported": [],
        },
        "experience": {
            "bullet_count": 2,
            "achievement_count": 1,
            "responsibility_count": 1,
            "quantified_bullets": 1,
            "findings": [],
        },
        "technical_depth": {
            "programming": ["python"],
            "machine_learning": [],
            "deep_learning": [],
            "generative_ai": [],
            "cloud": [],
            "mlops": [],
        },
        "structure": {"findings": []},
        "findings": [],
        "summary": {
            "strengths": ["Cached strength"],
            "top_priorities": [],
        },
    }

    cached_analysis = SimpleNamespace(analysis_result=cached_result)
    db = FakeDB(resume_version, cached_analysis=cached_analysis)
    provider = FakeProvider()

    monkeypatch.setattr(
        service,
        "create_resume_ai_provider",
        lambda: provider,
    )

    result = service.analyze_resume_version(
        db=db,
        user_id=resume_version.resume.user_id,
        resume_version_id=resume_version.id,
    )

    # The cached analysis was returned directly...
    assert result.summary.strengths == ["Cached strength"]

    # ...without calling the AI provider or persisting a new analysis.
    assert provider.resume_text is None
    assert db.added == []
    assert db.committed is False