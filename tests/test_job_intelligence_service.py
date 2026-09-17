from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.api.models import JobIntelligence
from apps.api.services.job_intelligence import service
from apps.api.services.job_intelligence.providers.openai_provider import (
    JobIntelligenceProviderError,
)


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, semantics=None, error=None):
        self.raw_jd_text = None
        self.deterministic_context = None
        self._semantics = semantics or {
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": "AI Engineer",
            "normalized_title_confidence": "high",
        }
        self._error = error

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        self.raw_jd_text = raw_jd_text
        self.deterministic_context = deterministic_context

        if self._error:
            raise self._error

        return self._semantics


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
    def __init__(self, job, cached_intelligence=None):
        self.job = job
        self.cached_intelligence = cached_intelligence
        self.added = []
        self.committed = False
        self.refreshed = []

    def query(self, model, *args, **kwargs):
        if model is JobIntelligence:
            return FakeQuery(self.cached_intelligence)
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
        title="Senior AI Engineer",
        description="3+ years of Python development required. PyTorch preferred.",
        requirements=None,
        responsibilities="- Build RAG pipelines",
        location="Remote - United States",
        country="USA",
        remote_type=None,
        employment_type="full_time",
        salary_min=150000,
        salary_max=180000,
        salary_currency="USD",
        contract_duration=None,
        contract_worker_type=None,
        source="test",
        source_url="https://example.com/job/1",
        application_url=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_generate_job_intelligence_persists_new_snapshot(monkeypatch):
    job = make_job()
    db = FakeDB(job)
    provider = FakeProvider()

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: provider
    )

    record = service.generate_job_intelligence(db, job_id=job.id)

    assert len(db.added) == 1
    assert db.added[0] is record
    assert db.committed is True
    assert record.job_id == job.id
    assert record.analysis_version == service.ANALYSIS_VERSION
    assert record.analyzer_version == service.ANALYZER_VERSION
    assert record.extraction_status == "complete"
    assert record.structured_intelligence["identity"]["original_title"] == (
        "Senior AI Engineer"
    )
    assert record.raw_jd_snapshot["title"] == "Senior AI Engineer"


def test_generate_job_intelligence_reuses_matching_snapshot(monkeypatch):
    """
    Same job + same JD content + same analyzer/prompt version must reuse
    the existing snapshot rather than recomputing (AJI-012 section 17).
    """
    job = make_job()
    fingerprint = service.compute_job_content_fingerprint(job)

    cached_record = SimpleNamespace(
        id=uuid4(),
        job_id=job.id,
        content_fingerprint=fingerprint,
        analyzer_version=service.ANALYZER_VERSION,
        prompt_version=service.PROMPT_VERSION,
    )

    db = FakeDB(job, cached_intelligence=cached_record)
    provider = FakeProvider()

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: provider
    )

    result = service.generate_job_intelligence(db, job_id=job.id)

    assert result is cached_record
    assert db.added == []
    assert db.committed is False
    assert provider.raw_jd_text is None


def test_fingerprint_changes_when_content_changes():
    job_a = make_job(description="Python required.")
    job_b = make_job(description="Java required.")

    assert service.compute_job_content_fingerprint(
        job_a
    ) != service.compute_job_content_fingerprint(job_b)


def test_fingerprint_stable_for_identical_content():
    job_a = make_job()
    job_b = make_job()

    assert service.compute_job_content_fingerprint(
        job_a
    ) == service.compute_job_content_fingerprint(job_b)


def test_raw_jd_snapshot_preserved(monkeypatch):
    job = make_job(description="Original JD text required.")
    db = FakeDB(job)
    provider = FakeProvider()

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: provider
    )

    record = service.generate_job_intelligence(db, job_id=job.id)

    assert record.raw_jd_snapshot["description"] == "Original JD text required."
    assert record.raw_jd_snapshot["source"] == "test"
    assert record.raw_jd_snapshot["source_url"] == "https://example.com/job/1"


def test_ai_failure_degrades_to_partial_deterministic_result(monkeypatch):
    """
    A failed AI call must never block or corrupt the deterministic
    result — it persists a "partial" snapshot instead (AJI-012 section
    28).
    """
    job = make_job()
    db = FakeDB(job)
    provider = FakeProvider(error=JobIntelligenceProviderError("boom"))

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: provider
    )

    record = service.generate_job_intelligence(db, job_id=job.id)

    assert record.extraction_status == "partial"
    assert record.model_provider is None
    assert record.model_name is None
    # Deterministic fields are still present and correct.
    assert any(
        item["canonical_skill"] == "python"
        for item in record.structured_intelligence["required_skills"]
    )
    assert db.committed is True


def test_generate_job_intelligence_rejects_missing_job():
    db = FakeDB(None)

    with pytest.raises(service.JobIntelligenceServiceError, match="Job not found"):
        service.generate_job_intelligence(db, job_id=uuid4())

    assert db.added == []
    assert db.committed is False


def test_get_latest_job_intelligence_does_not_recompute(monkeypatch):
    job = make_job()
    cached_record = SimpleNamespace(id=uuid4(), job_id=job.id)
    db = FakeDB(job, cached_intelligence=cached_record)

    def _fail_provider():
        raise AssertionError("AI provider must not be called on a read.")

    monkeypatch.setattr(service, "create_job_intelligence_provider", _fail_provider)

    result = service.get_latest_job_intelligence(db, job_id=job.id)

    assert result is cached_record
