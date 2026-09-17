"""End-to-end idempotency/versioning tests against a real database
session, complementing the FakeDB-based tests in
test_job_intelligence_service.py. These exercise the actual SQL
filtering (fingerprint + analyzer/prompt version) that a mocked query
object cannot meaningfully validate.
"""

from uuid import uuid4

from apps.api.models import Company, Job, JobIntelligence
from apps.api.services.job_intelligence import service


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        return {
            "normalized_title": "AI Engineer",
            "normalized_title_evidence": raw_jd_text.split("\n")[0],
            "normalized_title_confidence": "high",
        }


def _make_job(db, **overrides) -> Job:
    company = Company(
        id=uuid4(),
        name="Versioning Test Co",
        normalized_name="versioning test co",
    )
    db.add(company)
    db.flush()

    defaults = dict(
        id=uuid4(),
        company_id=company.id,
        title="AI Engineer",
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="3+ years of Python development required.",
        source="test",
    )
    defaults.update(overrides)

    job = Job(**defaults)
    db.add(job)
    db.flush()

    return job


def test_same_job_same_content_reuses_snapshot(db, monkeypatch):
    job = _make_job(db)

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: FakeProvider()
    )

    first = service.generate_job_intelligence(db, job_id=job.id)
    second = service.generate_job_intelligence(db, job_id=job.id)

    assert first.id == second.id

    count = (
        db.query(JobIntelligence)
        .filter(JobIntelligence.job_id == job.id)
        .count()
    )
    assert count == 1


def test_changed_jd_creates_new_snapshot_without_overwriting_history(
    db, monkeypatch
):
    job = _make_job(db)

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: FakeProvider()
    )

    first = service.generate_job_intelligence(db, job_id=job.id)
    first_fingerprint = first.content_fingerprint
    first_structured = dict(first.structured_intelligence)

    # The JD changes (e.g. re-discovery pulled an updated posting).
    job.description = "5+ years of Python development required."
    db.flush()

    second = service.generate_job_intelligence(db, job_id=job.id)

    assert second.id != first.id
    assert second.content_fingerprint != first_fingerprint

    # The historical snapshot is untouched.
    reloaded_first = (
        db.query(JobIntelligence).filter(JobIntelligence.id == first.id).one()
    )
    assert reloaded_first.structured_intelligence == first_structured

    count = (
        db.query(JobIntelligence)
        .filter(JobIntelligence.job_id == job.id)
        .count()
    )
    assert count == 2


def test_analyzer_version_bump_creates_new_snapshot(db, monkeypatch):
    job = _make_job(db)

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: FakeProvider()
    )

    first = service.generate_job_intelligence(db, job_id=job.id)

    # Simulate an analyzer version bump between requests.
    monkeypatch.setattr(service, "ANALYZER_VERSION", "2.0")

    second = service.generate_job_intelligence(db, job_id=job.id)

    assert second.id != first.id
    assert second.analyzer_version == "2.0"
    assert first.analyzer_version == "1.0"

    count = (
        db.query(JobIntelligence)
        .filter(JobIntelligence.job_id == job.id)
        .count()
    )
    assert count == 2


def test_get_latest_returns_most_recent_snapshot(db, monkeypatch):
    job = _make_job(db)

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: FakeProvider()
    )

    service.generate_job_intelligence(db, job_id=job.id)

    job.description = "5+ years of Python development required."
    db.flush()

    latest = service.generate_job_intelligence(db, job_id=job.id)

    fetched = service.get_latest_job_intelligence(db, job_id=job.id)

    assert fetched.id == latest.id


def test_raw_jd_snapshot_preserved_across_versions(db, monkeypatch):
    job = _make_job(db, description="Original text required.")

    monkeypatch.setattr(
        service, "create_job_intelligence_provider", lambda: FakeProvider()
    )

    first = service.generate_job_intelligence(db, job_id=job.id)
    assert first.raw_jd_snapshot["description"] == "Original text required."

    job.description = "Updated text required."
    db.flush()

    second = service.generate_job_intelligence(db, job_id=job.id)
    assert second.raw_jd_snapshot["description"] == "Updated text required."

    # The first snapshot's raw JD is untouched by the later edit.
    reloaded_first = (
        db.query(JobIntelligence).filter(JobIntelligence.id == first.id).one()
    )
    assert reloaded_first.raw_jd_snapshot["description"] == (
        "Original text required."
    )
