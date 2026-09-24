"""AJI-030 - the controlled development dataset, end to end.

Development dataset -> adapter -> canonical DiscoveredJob -> normalize ->
validate -> deduplicate -> persist -> active/expired filtering -> search ->
details -> Job Intelligence -> Resume <-> Job Match -> Application Tracking,
all through the existing AJI-024/028 pipeline and APIs, with no network,
API key, or real provider.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import (
    Job,
    Preference,
    Profile,
    Resume,
    ResumeVersion,
    SavedJob,
    User,
)
from apps.api.security import create_access_token
from apps.api.services.job_discovery_service import (
    JobDiscoveryTestProviderDisabledError,
    build_configured_source,
    run_configured_discovery,
)
from apps.api.services.job_intelligence import service as intelligence_service
from apps.api.services.job_intelligence.providers.openai_provider import (
    JobIntelligenceProviderError,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint
from services.job_discovery.pipeline import normalize_raw_jobs
from services.job_discovery.sources.development_dataset import (
    DATASET_PATH,
    DEVELOPMENT_DATASET_SOURCE,
    DevelopmentDatasetJobSource,
    load_dataset_records,
)
from services.job_discovery.sources.non_production import (
    NON_PRODUCTION_SOURCES,
    is_non_production_source,
)
from services.job_discovery.sources.test_fixture import TEST_FIXTURE_SOURCE


TODAY = datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc)
ANCHOR = datetime(2026, 9, 24, tzinfo=timezone.utc)

# The dataset's designed outcome (see development_dataset.json).
EXPECTED_FETCHED = 20
EXPECTED_INSERTED = 17
EXPECTED_DUPLICATES = 1
EXPECTED_REJECTED = 2
EXPIRED_IDS = {"dev-1016", "dev-1017"}
REJECTED_IDS = {"dev-1018", "dev-1019"}


@pytest.fixture(autouse=True)
def _discovery_settings(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_trigger_token", None)
    monkeypatch.setattr(settings, "job_discovery_greenhouse_board_token", None)
    monkeypatch.setattr(settings, "job_discovery_greenhouse_company_name", None)
    monkeypatch.setattr(settings, "job_discovery_provider", None)
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)


@pytest.fixture
def dev_mode(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_provider", "development_dataset")
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", True)


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class GroundedFakeProvider:
    """Stands in for the AI stage: returns only a title that is quoted
    verbatim from the JD, like a well-behaved provider."""

    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        first_line = raw_jd_text.split("\n")[0]
        return {
            "normalized_title": first_line,
            "normalized_title_evidence": first_line,
            "normalized_title_confidence": "high",
        }


class FailingProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        raise JobIntelligenceProviderError("no AI configured")


def _run_as_separate_request(db):
    session = Session(
        bind=db.connection(), join_transaction_mode="create_savepoint"
    )
    try:
        return run_configured_discovery(session)
    finally:
        session.close()


def _dev_jobs(db) -> dict[str, Job]:
    return {
        job.external_job_id: job
        for job in db.query(Job)
        .filter(Job.source == DEVELOPMENT_DATASET_SOURCE)
        .all()
    }


def _make_user(db, *, with_profile: bool = False) -> User:
    user = User(
        id=uuid4(),
        email=f"dev-dataset-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    if with_profile:
        db.add(
            Profile(
                id=uuid4(),
                user_id=user.id,
                full_name="Dev Dataset User",
                location="Austin, TX",
                years_experience=4.0,
                target_titles=["Machine Learning Engineer"],
            )
        )
        db.add(
            Preference(
                id=uuid4(),
                user_id=user.id,
                employment_types=["full_time"],
                locations=["Austin"],
                remote_preference="remote",
            )
        )
        db.flush()

    return user


def _add_resume(db, user: User) -> ResumeVersion:
    resume = Resume(
        id=uuid4(),
        user_id=user.id,
        filename="resume.txt",
        original_text="Machine learning engineer. Python, pandas, AWS.",
    )
    db.add(resume)
    db.flush()

    content_text = (
        "PROFESSIONAL SUMMARY\n"
        "Machine learning engineer with 4 years of experience.\n\n"
        "EXPERIENCE\n"
        "- Built forecasting models in Python with pandas and scikit-learn.\n"
        "- Deployed model services to AWS.\n\n"
        "SKILLS\n"
        "Python, pandas, scikit-learn, AWS, SQL\n"
    )
    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name="Master Resume",
        content_text=content_text,
        content_fingerprint=compute_content_fingerprint(content_text),
        original_filename="resume.txt",
        storage_path="/tmp/dev-dataset-resume.txt",
        is_master=True,
    )
    db.add(version)
    db.flush()

    return version


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _listed_dev_ids(client, user, **params) -> set[str]:
    response = client.get(
        "/jobs", params={"page_size": 100, **params}, headers=_auth(user)
    )
    assert response.status_code == 200
    return {
        job["source_job_id"]
        for job in response.json()["jobs"]
        if job["source"] == DEVELOPMENT_DATASET_SOURCE
    }


# ---------------------------------------------------------------------------
# The dataset itself
# ---------------------------------------------------------------------------


def test_dataset_is_explicitly_marked_synthetic():
    document = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    assert document["dataset"] == DEVELOPMENT_DATASET_SOURCE
    assert "SYNTHETIC DEVELOPMENT DATA" in document["notice"]
    for record in document["records"]:
        assert record["company"].endswith("(demo)")
        # No link to anything: nothing here can pass for a live posting.
        assert not re.search(r"https?://", json.dumps(record))


def test_dataset_covers_the_variation_the_workflow_needs():
    source = DevelopmentDatasetJobSource(now=TODAY)
    normalized, errors = normalize_raw_jobs(source, source.fetch_raw_jobs())
    valid = {
        job.source_job_id: job
        for job in normalized
        if job.source_job_id not in REJECTED_IDS
    }

    assert errors == []
    assert {job.employment_type for job in valid.values()} == {
        "full_time",
        "contract",
    }
    assert {job.remote_type for job in valid.values()} == {
        "remote",
        "hybrid",
        "onsite",
    }
    assert len({job.company for job in valid.values()}) >= 6
    assert len({job.title for job in valid.values()}) == len(valid)
    assert len({job.location for job in valid.values()}) >= 8
    assert any(job.salary_min is not None for job in valid.values())
    assert any(job.salary_min is None for job in valid.values())
    assert any(job.expires_at is None for job in valid.values())
    assert all(job.requirements and job.responsibilities for job in valid.values())
    contracts = [j for j in valid.values() if j.employment_type == "contract"]
    assert all(j.contract_duration and j.contract_worker_type for j in contracts)


def test_relative_dates_resolve_against_the_run_day():
    source = DevelopmentDatasetJobSource(now=TODAY)
    jobs = {
        job.source_job_id: job
        for job in normalize_raw_jobs(source, source.fetch_raw_jobs())[0]
    }

    assert jobs["dev-1001"].posted_at == ANCHOR - timedelta(days=2)
    assert jobs["dev-1001"].expires_at == ANCHOR + timedelta(days=28)
    assert jobs["dev-1009"].expires_at is None  # no stated expiry
    assert jobs["dev-1016"].expires_at == ANCHOR - timedelta(days=5)


def test_same_day_runs_are_identical_and_input_is_not_mutated():
    records = load_dataset_records()
    before = json.dumps(records, sort_keys=True)

    first = DevelopmentDatasetJobSource(now=TODAY, records=records)
    later = DevelopmentDatasetJobSource(
        now=TODAY.replace(hour=23), records=records
    )

    assert normalize_raw_jobs(first, first.fetch_raw_jobs())[0] == (
        normalize_raw_jobs(later, later.fetch_raw_jobs())[0]
    )
    assert json.dumps(records, sort_keys=True) == before


def test_normalization_maps_provider_style_values_onto_the_canonical_schema():
    source = DevelopmentDatasetJobSource(now=TODAY)
    jobs = {
        job.source_job_id: job
        for job in normalize_raw_jobs(source, source.fetch_raw_jobs())[0]
    }

    backend = jobs["dev-1001"]
    assert backend.source == DEVELOPMENT_DATASET_SOURCE
    assert backend.employment_type == "full_time"
    assert backend.remote_type == "hybrid"
    assert (backend.salary_min, backend.salary_max) == (150000.0, 185000.0)
    assert backend.salary_currency == "USD"
    assert backend.requirements.splitlines()[0] == (
        "5+ years of professional software engineering experience."
    )
    assert backend.source_url is None and backend.application_url is None

    contract = jobs["dev-1008"]  # "contractor" -> contract, no salary stated
    assert contract.employment_type == "contract"
    assert contract.salary_min is None and contract.salary_currency is None
    assert contract.contract_duration == "12 months"

    assert jobs["dev-1003"].remote_type == "onsite"  # "On-site"


def test_malformed_record_is_a_rejection_not_a_failed_batch():
    source = DevelopmentDatasetJobSource(
        now=TODAY, records=[*load_dataset_records()[:2], "not a record"]
    )

    normalized, errors = normalize_raw_jobs(source, source.fetch_raw_jobs())

    assert len(normalized) == 2
    assert len(errors) == 1


# ---------------------------------------------------------------------------
# Isolation from production configuration
# ---------------------------------------------------------------------------


def test_development_dataset_requires_the_test_mode_flag(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_provider", "development_dataset")

    with pytest.raises(JobDiscoveryTestProviderDisabledError) as exc_info:
        build_configured_source()

    assert exc_info.value.status_code == 503
    assert "development_dataset" in str(exc_info.value)


def test_dev_mode_selects_the_dataset_adapter(dev_mode):
    source = build_configured_source()

    assert isinstance(source, DevelopmentDatasetJobSource)
    assert source.is_test_provider is True


def test_every_test_provider_is_hidden_as_non_production():
    """A synthetic provider that could be selected but not hidden would
    surface as production data - pin the two lists together."""
    from apps.api.services.job_discovery_service import TEST_PROVIDERS

    for adapter_class in TEST_PROVIDERS.values():
        assert adapter_class.is_test_provider is True
        assert adapter_class.source_name in NON_PRODUCTION_SOURCES


def test_both_synthetic_sources_are_non_production():
    assert NON_PRODUCTION_SOURCES == {
        TEST_FIXTURE_SOURCE,
        DEVELOPMENT_DATASET_SOURCE,
    }
    assert is_non_production_source(DEVELOPMENT_DATASET_SOURCE)
    assert not is_non_production_source("greenhouse")
    assert not is_non_production_source(None)


# ---------------------------------------------------------------------------
# Ingestion -> validate -> dedupe -> persist
# ---------------------------------------------------------------------------


def test_first_run_counters(db, dev_mode):
    summary = run_configured_discovery(db)

    assert summary.source == DEVELOPMENT_DATASET_SOURCE
    assert summary.is_test_data is True
    assert summary.fetched == EXPECTED_FETCHED
    assert summary.normalized == EXPECTED_FETCHED
    assert summary.duplicates == EXPECTED_DUPLICATES
    assert summary.rejected == EXPECTED_REJECTED
    assert summary.inserted == EXPECTED_INSERTED
    assert summary.updated == 0
    reasons = " ".join(summary.rejected_reasons)
    assert "United States" in reasons
    assert "not meaningful" in reasons

    stored = _dev_jobs(db)
    assert set(stored) == {f"dev-{n}" for n in range(1001, 1018)}
    assert not REJECTED_IDS & set(stored)


def test_ingestion_through_the_existing_trigger_endpoint(
    client, db, dev_mode, monkeypatch
):
    """How a developer loads the dataset: the same authenticated trigger
    the scheduler uses - no API key, provider account or network."""
    monkeypatch.setattr(settings, "job_discovery_trigger_token", "dev-secret")

    response = client.post(
        "/internal/job-discovery/run",
        headers={"X-Discovery-Trigger-Token": "dev-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == DEVELOPMENT_DATASET_SOURCE
    assert body["is_test_data"] is True
    assert (body["fetched"], body["inserted"], body["duplicates"]) == (
        EXPECTED_FETCHED,
        EXPECTED_INSERTED,
        EXPECTED_DUPLICATES,
    )


def test_source_metadata_and_canonical_fields_persist(db, dev_mode):
    run_configured_discovery(db)
    job = _dev_jobs(db)["dev-1004"]

    assert job.source == DEVELOPMENT_DATASET_SOURCE
    assert job.submitted_by_user_id is None
    assert job.company.name == "Meridian Freight Systems (demo)"
    assert job.employment_type == "contract"
    assert job.remote_type == "remote"
    assert job.contract_duration == "6 months"
    assert job.contract_worker_type == "w2"
    assert job.posting_date is not None and job.posting_date.tzinfo is None
    assert job.expires_at is not None and job.expires_at.tzinfo is None
    assert job.identity_fingerprint


def test_repeat_run_updates_in_place_with_stable_ids(db, dev_mode):
    run_configured_discovery(db)
    first_ids = {key: job.id for key, job in _dev_jobs(db).items()}

    summary = _run_as_separate_request(db)
    db.expire_all()

    assert summary.inserted == 0
    assert summary.updated == EXPECTED_INSERTED
    assert summary.duplicates == EXPECTED_DUPLICATES
    assert {key: job.id for key, job in _dev_jobs(db).items()} == first_ids


# ---------------------------------------------------------------------------
# Search, active/expired, details, visibility
# ---------------------------------------------------------------------------


def test_expired_jobs_are_excluded_and_active_jobs_listed(client, db, dev_mode):
    run_configured_discovery(db)
    user = _make_user(db)

    listed = _listed_dev_ids(client, user)

    assert len(listed) == EXPECTED_INSERTED - len(EXPIRED_IDS)
    assert not EXPIRED_IDS & listed


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"employment_type": "contract"}, {"dev-1004", "dev-1008", "dev-1011"}),
        (
            {"remote_type": "remote"},
            {"dev-1002", "dev-1004", "dev-1008", "dev-1009", "dev-1014"},
        ),
        (
            {"remote_type": "onsite"},
            {"dev-1003", "dev-1007", "dev-1011", "dev-1013"},
        ),
        (
            {"remote_type": "hybrid"},
            {"dev-1001", "dev-1005", "dev-1006", "dev-1010", "dev-1012", "dev-1015"},
        ),
        ({"location": "austin"}, {"dev-1001", "dev-1006"}),
        ({"search": "machine learning"}, {"dev-1002"}),
        ({"search": "Lakeshore Mutual"}, {"dev-1007", "dev-1015"}),
        (
            {"employment_type": "full_time", "remote_type": "remote"},
            {"dev-1002", "dev-1009", "dev-1014"},
        ),
    ],
)
def test_search_filters(client, db, dev_mode, params, expected):
    run_configured_discovery(db)
    user = _make_user(db)

    assert _listed_dev_ids(client, user, **params) == expected


def test_job_details_return_canonical_data_flagged_as_test_data(
    client, db, dev_mode
):
    run_configured_discovery(db)
    user = _make_user(db)
    job = _dev_jobs(db)["dev-1001"]

    response = client.get(f"/jobs/{job.id}", headers=_auth(user))
    body = response.json()

    assert response.status_code == 200
    assert body["is_test_data"] is True
    assert body["origin"] == "discovered"
    assert body["source"] == DEVELOPMENT_DATASET_SOURCE
    assert body["source_job_id"] == "dev-1001"
    assert body["source_attribution"] is None
    assert body["source_url"] is None and body["application_url"] is None
    assert body["title"] == "Senior Backend Engineer"
    assert body["company"] == "Harborline Health (demo)"
    assert body["salary_min"] == 150000
    assert body["expires_at"] is not None
    assert "Deploy services to AWS" in body["responsibilities"]


def test_expired_job_remains_readable_by_id(client, db, dev_mode):
    run_configured_discovery(db)
    user = _make_user(db)
    expired = _dev_jobs(db)["dev-1016"]

    response = client.get(f"/jobs/{expired.id}", headers=_auth(user))

    assert response.status_code == 200
    assert response.json()["is_test_data"] is True


def test_dev_jobs_are_hidden_everywhere_when_test_mode_is_off(
    client, db, dev_mode, monkeypatch
):
    run_configured_discovery(db)
    user = _make_user(db)
    job = _dev_jobs(db)["dev-1001"]

    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)

    assert _listed_dev_ids(client, user) == set()
    assert client.get(f"/jobs/{job.id}", headers=_auth(user)).status_code == 404
    priority = client.get("/jobs/priority", headers=_auth(user))
    assert DEVELOPMENT_DATASET_SOURCE not in priority.text
    status = client.get("/job-discovery/status", headers=_auth(user)).json()
    assert status["test_mode"] is False
    # The only run so far was the development dataset's: not reported.
    assert status["last_run"] is None


# ---------------------------------------------------------------------------
# Job understanding (existing AJI-012 Job Intelligence)
# ---------------------------------------------------------------------------


def _jd_text(job: dict) -> str:
    return " ".join(
        " ".join(
            part or ""
            for part in (
                job["title"],
                job["location"],
                job["description"],
                job["requirements"],
                job["responsibilities"],
            )
        ).split()
    )


def test_job_intelligence_is_grounded_in_the_dev_job(
    client, db, dev_mode, monkeypatch
):
    monkeypatch.setattr(
        intelligence_service,
        "create_job_intelligence_provider",
        lambda: GroundedFakeProvider(),
    )
    run_configured_discovery(db)
    user = _make_user(db)
    job_id = _dev_jobs(db)["dev-1001"].id
    job = client.get(f"/jobs/{job_id}", headers=_auth(user)).json()

    response = client.post(f"/jobs/{job_id}/intelligence", headers=_auth(user))
    assert response.status_code == 200
    body = response.json()
    intel = body["intelligence"]

    assert body["extraction_status"] == "complete"
    assert body["source"] == DEVELOPMENT_DATASET_SOURCE
    skills = {s["canonical_skill"] for s in intel["required_skills"]}
    assert {"python", "sql", "docker", "aws"} <= skills
    assert "kubernetes" in {s["canonical_skill"] for s in intel["preferred_skills"]}
    years = [e["minimum_years"] for e in intel["required_experience"]]
    assert 5 in years
    assert intel["responsibilities"]
    assert intel["employment"]["employment_type"] == "full_time"
    assert intel["location"]["remote_type"] == "hybrid"
    assert intel["compensation"]["salary_min"] == 150000

    # Grounded: every piece of evidence is quoted from the job itself.
    jd = _jd_text(job)
    evidence = [
        item["evidence_text"]
        for key in (
            "required_skills",
            "preferred_skills",
            "required_experience",
            "responsibilities",
        )
        for item in intel[key]
    ]
    assert evidence
    for text in evidence:
        assert " ".join(text.split()) in jd

    # Idempotent: the same job content reuses the same snapshot.
    again = client.post(f"/jobs/{job_id}/intelligence", headers=_auth(user))
    assert again.json()["id"] == body["id"]
    read = client.get(f"/jobs/{job_id}/intelligence", headers=_auth(user))
    assert read.json()["id"] == body["id"]


def test_job_intelligence_without_an_ai_provider_keeps_deterministic_facts(
    client, db, dev_mode, monkeypatch
):
    """Zero-cost development: with no AI configured, the deterministic
    extraction still produces a partial, evidence-backed snapshot."""
    monkeypatch.setattr(
        intelligence_service,
        "create_job_intelligence_provider",
        lambda: FailingProvider(),
    )
    run_configured_discovery(db)
    user = _make_user(db)
    job_id = _dev_jobs(db)["dev-1004"].id

    response = client.post(f"/jobs/{job_id}/intelligence", headers=_auth(user))

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "partial"
    assert body["intelligence"]["employment"]["employment_type"] == "contract"
    assert "sql" in {
        s["canonical_skill"] for s in body["intelligence"]["required_skills"]
    }


# ---------------------------------------------------------------------------
# Resume <-> Job Match (existing deterministic matcher)
# ---------------------------------------------------------------------------


def test_resume_match_against_a_dev_job_is_explainable(client, db, dev_mode):
    run_configured_discovery(db)
    user = _make_user(db, with_profile=True)
    version = _add_resume(db, user)
    job_id = _dev_jobs(db)["dev-1002"].id  # Machine Learning Engineer

    response = client.post(f"/jobs/{job_id}/match", headers=_auth(user))

    assert response.status_code == 200
    body = response.json()
    assert body["resume_version_id"] == str(version.id)
    assert 0 <= body["score"] <= 100
    assert body["confidence"] in {"high", "medium", "low"}

    matched = {
        item["skill"]
        for item in body["must_have_matches"] + body["preferred_matches"]
    }
    gaps = {
        item["skill"]
        for item in body["must_have_gaps"] + body["preferred_gaps"]
    }

    # Skills on the resume and in the job are credited, with evidence...
    assert {"python", "pandas", "scikit-learn", "aws"} <= matched
    assert all(item["evidence"] for item in body["must_have_matches"])
    # ...and job skills the resume never mentions are gaps, not invented.
    assert {"pytorch", "spark"} <= gaps
    assert not matched & gaps

    read = client.get(f"/jobs/{job_id}/match", headers=_auth(user))
    assert read.status_code == 200
    assert read.json()["id"] == body["id"]


# ---------------------------------------------------------------------------
# Application tracking (existing SavedJob workflow)
# ---------------------------------------------------------------------------


def test_dev_job_enters_the_application_workflow(client, db, dev_mode):
    run_configured_discovery(db)
    user = _make_user(db)
    job_id = str(_dev_jobs(db)["dev-1003"].id)

    created = client.post(
        "/applications", json={"job_id": job_id}, headers=_auth(user)
    )
    assert created.status_code == 201
    application = created.json()
    assert application["status"] == "saved"
    assert application["job"]["is_test_data"] is True
    assert application["job"]["application_url"] is None

    updated = client.patch(
        f"/applications/{application['id']}",
        json={"status": "applied"},
        headers=_auth(user),
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "applied"

    detail = client.get(
        f"/applications/{application['id']}", headers=_auth(user)
    ).json()
    assert [event["status"] for event in detail["status_history"]] == [
        "saved",
        "applied",
    ]
    assert detail["job"]["is_test_data"] is True


def test_rerunning_discovery_keeps_application_relationships(
    client, db, dev_mode
):
    run_configured_discovery(db)
    user = _make_user(db)
    job = _dev_jobs(db)["dev-1005"]
    created = client.post(
        "/applications", json={"job_id": str(job.id)}, headers=_auth(user)
    ).json()

    _run_as_separate_request(db)
    db.expire_all()

    saved = db.query(SavedJob).filter(SavedJob.id == created["id"]).one()
    assert saved.job_id == job.id
    listed = client.get("/applications", headers=_auth(user)).json()
    assert [a["job"]["id"] for a in listed] == [str(job.id)]


def test_non_synthetic_application_is_not_flagged(client, db):
    user = _make_user(db)
    from apps.api.models import Company

    company = Company(id=uuid4(), name="Real Co", normalized_name="real co")
    db.add(company)
    db.flush()
    job = Job(
        id=uuid4(),
        company_id=company.id,
        title="Engineer",
        country="USA",
        description="A regular discovered posting for this test.",
        source="greenhouse",
    )
    db.add(job)
    db.flush()

    created = client.post(
        "/applications", json={"job_id": str(job.id)}, headers=_auth(user)
    )

    assert created.status_code == 201
    assert created.json()["job"]["is_test_data"] is False
