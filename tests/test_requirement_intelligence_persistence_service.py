"""FakeDB-based unit tests for the Requirement Intelligence persistence
service (AJI-020B), mirroring test_job_intelligence_service.py's split:
this file covers wiring/error-path behavior with a mocked query object;
test_requirement_intelligence_persistence_versioning.py covers the real
SQL filtering a mocked query object cannot meaningfully validate.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from apps.api.models import RequirementIntelligence
from apps.api.services.requirement_intelligence import persistence_service
from apps.api.services.requirement_intelligence.service import (
    RequirementIntelligenceServiceError,
)


class FakeQuery:
    def __init__(self, results):
        self._results = list(results) if isinstance(results, list) else [results]

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._results[0] if self._results else None


class FakeDB:
    def __init__(self, job, cached_requirement_intelligence=None):
        self.job = job
        self.cached = cached_requirement_intelligence
        self.added = []
        self.committed = False
        self.refreshed = []

    def query(self, model, *args, **kwargs):
        if model is RequirementIntelligence:
            return FakeQuery(self.cached)
        return FakeQuery(self.job)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True

    def refresh(self, item):
        self.refreshed.append(item)


def make_job(**overrides):
    defaults = dict(
        id=uuid4(),
        title="Senior Backend Engineer",
        description="5+ years of Python experience required.",
        requirements=None,
        responsibilities="- Build and maintain services",
        location="Remote",
        salary_min=None,
        salary_max=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _patch_settings(monkeypatch, *, ai_provider="openai", ai_model="test-model"):
    monkeypatch.setattr(persistence_service.settings, "ai_provider", ai_provider)
    monkeypatch.setattr(persistence_service.settings, "ai_model", ai_model)


def test_generate_persists_new_snapshot(monkeypatch):
    job = make_job()
    db = FakeDB(job)
    user_id = uuid4()

    with patch(
        "apps.api.services.requirement_intelligence.persistence_service."
        "build_requirement_intelligence"
    ) as mock_build:
        from apps.api.services.requirement_intelligence.contracts import (
            RequirementIntelligenceResult,
            TitleSeniorityInfo,
        )

        mock_build.return_value = RequirementIntelligenceResult(
            analysis_version="1.0",
            analyzer_version="1.0",
            prompt_version="1.0",
            model_provider="openai",
            model_name="test-model",
            extraction_status="complete",
            source_id=str(job.id),
            identity=TitleSeniorityInfo(original_title=job.title),
        )

        record = persistence_service.generate_requirement_intelligence(
            db, user_id=user_id, job_id=job.id
        )

    assert len(db.added) == 1
    assert db.added[0] is record
    assert db.committed is True
    assert record.user_id == user_id
    assert record.job_id == job.id
    assert record.analysis_version == "1.0"
    assert record.model_provider == "openai"
    assert record.model_name == "test-model"
    assert record.extraction_status == "complete"
    assert record.raw_jd_snapshot["title"] == job.title
    assert record.structured_intelligence["identity"]["original_title"] == (
        job.title
    )


def test_generate_reuses_matching_snapshot_without_calling_pipeline(
    monkeypatch,
):
    job = make_job()
    _patch_settings(monkeypatch)
    fingerprint = persistence_service.compute_requirement_content_fingerprint(job)
    user_id = uuid4()

    cached_record = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        job_id=job.id,
        content_fingerprint=fingerprint,
        analyzer_version=(
            persistence_service.requirement_intelligence_service.ANALYZER_VERSION
        ),
        prompt_version=(
            persistence_service.requirement_intelligence_service.PROMPT_VERSION
        ),
        model_provider="openai",
        model_name="test-model",
    )

    db = FakeDB(job, cached_requirement_intelligence=cached_record)

    with patch(
        "apps.api.services.requirement_intelligence.persistence_service."
        "build_requirement_intelligence"
    ) as mock_build:
        record = persistence_service.generate_requirement_intelligence(
            db, user_id=user_id, job_id=job.id
        )

        mock_build.assert_not_called()

    assert record is cached_record
    assert db.added == []
    assert db.committed is False


def test_job_not_found_raises_persistence_error():
    db = FakeDB(job=None)

    with pytest.raises(
        persistence_service.RequirementIntelligencePersistenceError
    ) as excinfo:
        persistence_service.generate_requirement_intelligence(
            db, user_id=uuid4(), job_id=uuid4()
        )

    assert excinfo.value.status_code == 404


def test_deterministic_failure_propagates_as_persistence_error():
    job = make_job()
    db = FakeDB(job)

    with patch(
        "apps.api.services.requirement_intelligence.persistence_service."
        "build_requirement_intelligence",
        side_effect=RequirementIntelligenceServiceError(
            "boom", status_code=503
        ),
    ):
        with pytest.raises(
            persistence_service.RequirementIntelligencePersistenceError
        ) as excinfo:
            persistence_service.generate_requirement_intelligence(
                db, user_id=uuid4(), job_id=job.id
            )

    assert excinfo.value.status_code == 503
    assert db.added == []
    assert db.committed is False


def test_fingerprint_scoped_to_pipeline_relevant_fields_only():
    job_a = make_job(salary_min=100000, location="Remote")
    job_b = make_job(
        id=job_a.id,
        title=job_a.title,
        description=job_a.description,
        requirements=job_a.requirements,
        responsibilities=job_a.responsibilities,
        salary_min=999999,
        location="Onsite - New York",
    )

    fingerprint_a = persistence_service.compute_requirement_content_fingerprint(
        job_a
    )
    fingerprint_b = persistence_service.compute_requirement_content_fingerprint(
        job_b
    )

    assert fingerprint_a == fingerprint_b


def test_fingerprint_changes_when_analyzed_content_changes():
    job_a = make_job(description="5+ years of Python experience required.")
    job_b = make_job(description="5+ years of Java experience required.")

    fingerprint_a = persistence_service.compute_requirement_content_fingerprint(
        job_a
    )
    fingerprint_b = persistence_service.compute_requirement_content_fingerprint(
        job_b
    )

    assert fingerprint_a != fingerprint_b


def test_fingerprint_is_stable_and_deterministic():
    job = make_job()

    first = persistence_service.compute_requirement_content_fingerprint(job)
    second = persistence_service.compute_requirement_content_fingerprint(job)

    assert first == second
    assert len(first) == 64  # sha256 hex digest
