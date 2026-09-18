"""End-to-end idempotency/versioning tests against a real database
session (AJI-020B), complementing the FakeDB-based tests in
test_requirement_intelligence_persistence_service.py. These exercise the
actual SQL filtering (fingerprint + analyzer/prompt version + model
identity) a mocked query object cannot meaningfully validate — mirrors
test_job_intelligence_versioning.py's structure.
"""

from uuid import uuid4

from apps.api.models import Company, Job, RequirementIntelligence, User
from apps.api.services.requirement_intelligence import persistence_service


def _make_job(db, **overrides) -> Job:
    company = Company(
        id=uuid4(),
        name="Requirement Intelligence Versioning Co",
        normalized_name="requirement intelligence versioning co",
    )
    db.add(company)
    db.flush()

    defaults = dict(
        id=uuid4(),
        company_id=company.id,
        title="Senior Backend Engineer",
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type="full_time",
        description="5+ years of Python experience required.",
        source="test",
    )
    defaults.update(overrides)

    job = Job(**defaults)
    db.add(job)
    db.flush()

    return job


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"req-intel-versioning-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def _patch_settings(monkeypatch, *, ai_provider="openai", ai_model="test-model"):
    monkeypatch.setattr(persistence_service.settings, "ai_provider", ai_provider)
    monkeypatch.setattr(persistence_service.settings, "ai_model", ai_model)


class FakeProvider:
    """Mirrors the real `OpenAIRequirementIntelligenceProvider`'s
    settings-derived `model_name` (rather than hardcoding one), so a
    test that patches `settings.ai_model` between calls observes the
    same model-identity change a real provider construction would."""

    provider_name = "openai"

    def __init__(self, *, model_name: str) -> None:
        self.model_name = model_name

    def generate_requirement_semantics(self, *, raw_jd_text, deterministic_context):
        return {
            "normalized_title": "Backend Engineer",
            "normalized_title_evidence": raw_jd_text.split("\n")[0],
            "normalized_title_confidence": "high",
        }


def _patch_provider(monkeypatch):
    monkeypatch.setattr(
        "apps.api.services.requirement_intelligence.service."
        "create_requirement_intelligence_provider",
        lambda: FakeProvider(model_name=persistence_service.settings.ai_model),
    )


def test_same_user_job_content_reuses_snapshot(db, monkeypatch):
    job = _make_job(db)
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    first = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )
    second = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    assert first.id == second.id

    count = (
        db.query(RequirementIntelligence)
        .filter(
            RequirementIntelligence.user_id == user.id,
            RequirementIntelligence.job_id == job.id,
        )
        .count()
    )
    assert count == 1


def test_changed_jd_creates_new_snapshot_without_overwriting_history(
    db, monkeypatch
):
    job = _make_job(db)
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    first = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )
    first_fingerprint = first.content_fingerprint
    first_structured = dict(first.structured_intelligence)

    job.description = "8+ years of Python experience required."
    db.flush()

    second = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    assert second.id != first.id
    assert second.content_fingerprint != first_fingerprint

    reloaded_first = (
        db.query(RequirementIntelligence)
        .filter(RequirementIntelligence.id == first.id)
        .one()
    )
    assert reloaded_first.structured_intelligence == first_structured

    count = (
        db.query(RequirementIntelligence)
        .filter(
            RequirementIntelligence.user_id == user.id,
            RequirementIntelligence.job_id == job.id,
        )
        .count()
    )
    assert count == 2


def test_irrelevant_job_edit_does_not_create_a_new_snapshot(db, monkeypatch):
    """Editing a Job field the pipeline never reads (salary/location)
    must not bust the cache — see
    persistence_service.compute_requirement_content_fingerprint's
    docstring for why the fingerprint is scoped narrowly."""
    job = _make_job(db)
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    first = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    job.salary_min = 999999
    job.location = "Onsite - New York"
    db.flush()

    second = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    assert second.id == first.id


def test_analyzer_version_bump_creates_new_snapshot(db, monkeypatch):
    job = _make_job(db)
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    first = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    monkeypatch.setattr(
        persistence_service.requirement_intelligence_service,
        "ANALYZER_VERSION",
        "2.0",
    )

    second = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    assert second.id != first.id

    count = (
        db.query(RequirementIntelligence)
        .filter(
            RequirementIntelligence.user_id == user.id,
            RequirementIntelligence.job_id == job.id,
        )
        .count()
    )
    assert count == 2


def test_prompt_version_bump_creates_new_snapshot(db, monkeypatch):
    job = _make_job(db)
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    first = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    monkeypatch.setattr(
        persistence_service.requirement_intelligence_service,
        "PROMPT_VERSION",
        "2.0",
    )

    second = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    assert second.id != first.id


def test_model_configuration_change_creates_new_snapshot(db, monkeypatch):
    job = _make_job(db)
    user = _make_user(db)
    _patch_settings(monkeypatch, ai_model="test-model")
    _patch_provider(monkeypatch)

    first = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )
    assert first.model_name == "test-model"

    _patch_settings(monkeypatch, ai_model="a-newer-model")

    second = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    assert second.id != first.id

    count = (
        db.query(RequirementIntelligence)
        .filter(
            RequirementIntelligence.user_id == user.id,
            RequirementIntelligence.job_id == job.id,
        )
        .count()
    )
    assert count == 2


def test_get_latest_returns_most_recent_snapshot(db, monkeypatch):
    job = _make_job(db)
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    job.description = "9+ years of Python experience required."
    db.flush()

    latest = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    fetched = persistence_service.get_latest_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    assert fetched.id == latest.id


def test_raw_jd_snapshot_preserved_across_versions(db, monkeypatch):
    job = _make_job(db, description="Original text required.")
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    first = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )
    assert first.raw_jd_snapshot["description"] == "Original text required."

    job.description = "Updated text required."
    db.flush()

    second = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )
    assert second.raw_jd_snapshot["description"] == "Updated text required."

    reloaded_first = (
        db.query(RequirementIntelligence)
        .filter(RequirementIntelligence.id == first.id)
        .one()
    )
    assert reloaded_first.raw_jd_snapshot["description"] == (
        "Original text required."
    )


def test_full_ajI_020a_result_survives_persistence_without_loss(db, monkeypatch):
    """The full AJI-020A contract (requirements, relationships, quality
    diagnostics, security diagnostics, provenance) must round-trip
    losslessly through persistence."""
    job = _make_job(
        db,
        description=(
            "5+ years of Python experience required. Python or Java "
            "required. Bachelor's degree in Computer Science required. "
            "AWS or equivalent cloud experience required. A background "
            "check is required."
        ),
        responsibilities="- Build and maintain backend services",
    )
    user = _make_user(db)
    _patch_settings(monkeypatch)
    _patch_provider(monkeypatch)

    from apps.api.services.requirement_intelligence.deterministic import (
        RawRequirementSource,
        extract_deterministic,
    )

    direct = extract_deterministic(
        RawRequirementSource(
            title=job.title,
            description=job.description,
            requirements=job.requirements,
            responsibilities=job.responsibilities,
        )
    )

    record = persistence_service.generate_requirement_intelligence(
        db, user_id=user.id, job_id=job.id
    )

    persisted = record.structured_intelligence

    assert len(persisted["requirements"]) == len(direct.requirements)
    assert len(persisted["relationships"]) == len(direct.relationships)
    assert len(persisted["screening_constraints"]) == len(
        direct.screening_constraints
    )
    assert (
        persisted["quality"]["duplicate_groups"]
        == [d.model_dump(mode="json") for d in direct.duplicate_groups]
    )

    # Provenance survives: every source_span's text is the exact
    # substring of the job's own description/requirements/responsibilities.
    full_text = "\n".join(
        part
        for part in [job.description, job.requirements, job.responsibilities]
        if part
    )
    for item in persisted["requirements"]:
        span = item.get("source_span")
        if span is None:
            continue
        assert full_text[span["start"] : span["end"]] == span["text"]

    # Re-validating the persisted JSON against the AJI-020A contract
    # itself proves nothing was dropped or corrupted in the round trip.
    from apps.api.services.requirement_intelligence.contracts import (
        RequirementIntelligenceResult,
    )

    revalidated = RequirementIntelligenceResult.model_validate(persisted)
    assert len(revalidated.requirements) == len(direct.requirements)
