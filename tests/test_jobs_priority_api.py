"""AJI-025 - GET /jobs/priority over a real database.

Match / ATS rows are inserted directly (the exact shape their services
persist) so each scenario controls its evidence precisely; the last tests
run the real Job Match and ATS Alignment services end to end.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from apps.api.config import settings
from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import (
    ApplicationStatusEvent,
    AtsAlignmentResult,
    Company,
    GapAnalysis,
    Job,
    JobEligibilityResult,
    JobIntelligence,
    JobMatchResult,
    Preference,
    Profile,
    RequirementIntelligence,
    Resume,
    ResumeVersion,
    SavedJob,
    User,
)
from apps.api.security import create_access_token
from apps.api.services.job_intelligence import service as job_intelligence_service
from apps.api.services.requirement_intelligence import (
    service as requirement_intelligence_service,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint
from services.ats_alignment.engine import ENGINE_VERSION as ATS_ENGINE_VERSION
from services.job_discovery.sources.test_fixture import TEST_FIXTURE_SOURCE
from services.job_matching.scorer import ENGINE_VERSION as MATCH_ENGINE_VERSION


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def no_test_provider(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)


def make_user(db, *, employment_types=None, remote_preference=None):
    user = User(
        id=uuid4(),
        email=f"priority-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    db.add(Profile(id=uuid4(), user_id=user.id, years_experience=3.0))
    db.add(
        Preference(
            id=uuid4(),
            user_id=user.id,
            employment_types=employment_types,
            remote_preference=remote_preference,
        )
    )
    db.flush()

    return user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def make_resume(db, user, names=("Master Resume", "Tailored Resume")):
    resume = Resume(
        id=uuid4(),
        user_id=user.id,
        filename=f"{user.email}-resume.txt",
        original_text="Python engineer.",
    )
    db.add(resume)
    db.flush()

    versions = []
    for index, name in enumerate(names):
        text = f"EXPERIENCE\n- {name}: built Python services.\n"
        version = ResumeVersion(
            id=uuid4(),
            resume_id=resume.id,
            name=name,
            content_text=text,
            content_fingerprint=compute_content_fingerprint(text),
            original_filename="resume.txt",
            storage_path="/tmp/priority-resume.txt",
            is_master=index == 0,
        )
        db.add(version)
        versions.append(version)

    db.flush()
    return versions


_company = None


def make_job(
    db,
    *,
    title="Engineer",
    employment_type="full_time",
    submitted_by=None,
    source="greenhouse",
    posting_date=None,
    is_active=True,
    company_name="Priority Test Co",
    expires_at=None,
):
    company = Company(
        id=uuid4(), name=company_name, normalized_name=company_name.lower()
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title=title,
        location="Remote",
        country="USA",
        remote_type="remote",
        employment_type=employment_type,
        description="Build Python services for customers.",
        requirements="3+ years of Python.",
        source="user_submitted" if submitted_by else source,
        submitted_by_user_id=submitted_by.id if submitted_by else None,
        posting_date=posting_date,
        is_active=is_active,
        expires_at=expires_at,
    )
    db.add(job)
    db.flush()
    return job


def make_ji(db, job, *, created_at=None):
    snapshot = JobIntelligence(
        id=uuid4(),
        job_id=job.id,
        content_fingerprint=uuid4().hex + uuid4().hex,
        raw_jd_snapshot={"title": job.title},
        source=job.source,
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.1",
        extraction_status="partial",
        structured_intelligence={},
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def make_ri(db, user, job, *, created_at=None):
    snapshot = RequirementIntelligence(
        id=uuid4(),
        user_id=user.id,
        job_id=job.id,
        content_fingerprint=uuid4().hex + uuid4().hex,
        raw_jd_snapshot={"title": job.title},
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        extraction_status="partial",
        structured_intelligence={},
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def make_match(db, user, job, version, score, ji, *, engine=MATCH_ENGINE_VERSION):
    record = JobMatchResult(
        id=uuid4(),
        user_id=user.id,
        job_id=job.id,
        resume_version_id=version.id,
        job_intelligence_id=ji.id if ji else None,
        job_content_fingerprint=ji.content_fingerprint if ji else None,
        engine_version=engine,
        score=score,
        confidence="medium",
        result={
            "must_have_matches": [{"skill": "python"}, {"skill": "sql"}],
            "must_have_gaps": [{"skill": "kubernetes"}],
            "preferred_matches": [],
            "preferred_gaps": [],
            "components": [],
            "strengths": [],
            "skill_gaps": ["kubernetes"],
        },
    )
    db.add(record)
    db.flush()
    return record


def make_ats(db, user, job, version, score, ji, ri, *, engine=ATS_ENGINE_VERSION):
    record = AtsAlignmentResult(
        id=uuid4(),
        user_id=user.id,
        job_id=job.id,
        resume_version_id=version.id,
        job_intelligence_id=ji.id,
        job_content_fingerprint=ji.content_fingerprint,
        requirement_intelligence_id=ri.id if ri else None,
        requirement_intelligence_fingerprint=ri.content_fingerprint if ri else None,
        engine_version=engine,
        overall_score=score,
        confidence="medium",
        result={
            "scoring_version": "weighted-1.0",
            "must_have_total": 4,
            "must_have_matched": 3,
            "preferred_total": 0,
            "preferred_matched": 0,
            "requirement_results": [],
        },
    )
    db.add(record)
    db.flush()
    return record


def analyze(db, user, job, version, *, match=None, ats=None):
    """Persist a Job Match and/or ATS Alignment against current snapshots."""
    ji = make_ji(db, job)
    ri = make_ri(db, user, job)
    records = {}
    if match is not None:
        records["match"] = make_match(db, user, job, version, match, ji)
    if ats is not None:
        records["ats"] = make_ats(db, user, job, version, ats, ji, ri)
    return records


def get_priority(client, user, **params):
    response = client.get("/jobs/priority", headers=auth(user), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def item_for(body, job):
    matches = [item for item in body["items"] if item["job"]["id"] == str(job.id)]
    assert len(matches) <= 1
    return matches[0] if matches else None


def ids(body):
    return [item["job"]["id"] for item in body["items"]]


# ---------------------------------------------------------------------------
# Authentication and contract
# ---------------------------------------------------------------------------


def test_priority_requires_authentication(client):
    assert client.get("/jobs/priority").status_code == 401


def test_priority_is_not_mistaken_for_a_job_id(client, db):
    user = make_user(db)
    body = get_priority(client, user)
    assert "items" in body


def test_contract_shape(client, db):
    user = make_user(db)
    versions = make_resume(db, user)
    job = make_job(db, title="Backend Engineer")
    records = analyze(db, user, job, versions[0], match=72.5, ats=64)

    body = get_priority(client, user)

    assert body["engine_version"] == "1.0.0"
    assert body["ordering"] == [
        "hard_eligibility",
        "job_match_score",
        "ats_alignment_score",
        "posting_date",
        "job_id",
    ]
    assert body["user_id"] == str(user.id)
    assert body["resume_version"]["id"] == str(versions[0].id)
    assert body["resume_version"]["name"] == "Master Resume"
    datetime.fromisoformat(body["generated_at"])

    item = item_for(body, job)
    assert item["rank"] == 1
    assert item["state"] == "ranked"
    assert item["eligibility_status"] == "eligible"
    assert item["job"]["title"] == "Backend Engineer"
    assert "score" not in item and "priority_score" not in item

    inputs = item["inputs"]
    assert inputs["eligibility"]["status"] == "eligible"
    assert inputs["job_match"]["id"] == str(records["match"].id)
    assert inputs["job_match"]["score"] == 72.5
    assert inputs["job_match"]["current"] is True
    assert inputs["ats_alignment"]["id"] == str(records["ats"].id)
    assert inputs["ats_alignment"]["overall_score"] == 64
    assert inputs["ats_alignment"]["current"] is True

    messages = [reason["message"] for reason in item["reasons"]]
    assert "Job Match 73%." in messages
    assert "Job Match found 2 of 3 required skills." in messages
    assert "ATS Alignment 64% - 3 of 4 must-have requirements demonstrated." in messages


# ---------------------------------------------------------------------------
# Ordering and Hard Eligibility
# ---------------------------------------------------------------------------


def test_orders_by_eligibility_then_match_then_ats(client, db):
    user = make_user(db, employment_types=["full_time"])
    version = make_resume(db, user)[0]

    top = make_job(db, title="Top")
    tie_high_ats = make_job(db, title="Tie high ATS")
    tie_low_ats = make_job(db, title="Tie low ATS")
    unknown = make_job(db, title="Unknown type", employment_type=None)
    not_ready = make_job(db, title="No match")
    excluded = make_job(db, title="Contract", employment_type="contract")

    analyze(db, user, top, version, match=90, ats=10)
    analyze(db, user, tie_high_ats, version, match=70, ats=80)
    analyze(db, user, tie_low_ats, version, match=70, ats=30)
    analyze(db, user, unknown, version, match=99, ats=99)
    analyze(db, user, not_ready, version, ats=95)
    analyze(db, user, excluded, version, match=100, ats=100)

    body = get_priority(client, user)

    assert ids(body) == [
        str(j.id)
        for j in [top, tie_high_ats, tie_low_ats, unknown, not_ready, excluded]
    ]
    assert [item["rank"] for item in body["items"]] == [1, 2, 3, 4, None, None]
    assert [item["state"] for item in body["items"]] == [
        "ranked", "ranked", "ranked", "ranked", "not_ready", "excluded",
    ]
    assert body["counts"] == {
        "ranked": 4,
        "partial": 0,
        "not_ready": 1,
        "excluded": 1,
        "unanalyzed": 0,
    }


def test_ineligible_job_is_excluded_even_with_perfect_scores(client, db):
    user = make_user(db, employment_types=["full_time"])
    version = make_resume(db, user)[0]
    job = make_job(db, employment_type="contract")
    analyze(db, user, job, version, match=100, ats=100)

    item = item_for(get_priority(client, user), job)

    assert item["state"] == "excluded"
    assert item["rank"] is None
    assert item["eligibility_status"] == "ineligible"
    assert [f["code"] for f in item["blocking_factors"]] == ["eligibility_failed"]
    assert "contract" in item["blocking_factors"][0]["message"]
    assert item["inputs"]["eligibility"]["failed_constraints"] == ["employment_type"]


def test_unknown_eligibility_stays_unknown(client, db):
    user = make_user(db, employment_types=["full_time"])
    version = make_resume(db, user)[0]
    job = make_job(db, employment_type=None)
    analyze(db, user, job, version, match=80, ats=80)

    item = item_for(get_priority(client, user), job)

    assert item["eligibility_status"] == "unknown"
    assert item["inputs"]["eligibility"]["unknown_constraints"] == ["employment_type"]
    assert item["rank"] == 1
    codes = [reason["code"] for reason in item["reasons"]]
    assert "eligibility_unknown" in codes


def test_eligibility_is_evaluated_fresh_from_current_preferences(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db, employment_type="full_time")
    analyze(db, user, job, version, match=80, ats=80)

    assert item_for(get_priority(client, user), job)["state"] == "ranked"

    user.preferences.employment_types = ["contract"]
    db.flush()

    assert item_for(get_priority(client, user), job)["state"] == "excluded"


# ---------------------------------------------------------------------------
# Missing / incomplete / out-of-date analysis
# ---------------------------------------------------------------------------


def test_missing_ats_is_partial(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db)
    analyze(db, user, job, version, match=60)

    item = item_for(get_priority(client, user), job)

    assert item["state"] == "partial"
    assert item["rank"] == 1
    assert item["inputs"]["ats_alignment"] is None
    assert "ats_missing" in [reason["code"] for reason in item["reasons"]]


def test_missing_match_is_not_ready_and_never_scored(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db)
    analyze(db, user, job, version, ats=88)

    item = item_for(get_priority(client, user), job)

    assert item["state"] == "not_ready"
    assert item["rank"] is None
    assert item["inputs"]["job_match"] is None
    assert [f["code"] for f in item["blocking_factors"]] == ["job_match_missing"]


def test_unanalyzed_jobs_are_counted_not_listed(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    analyzed = make_job(db)
    make_job(db)
    make_job(db)
    analyze(db, user, analyzed, version, match=50, ats=50)

    body = get_priority(client, user)
    visible_total = client.get("/jobs", headers=auth(user)).json()["pagination"]["total"]

    assert ids(body) == [str(analyzed.id)]
    assert body["counts"]["unanalyzed"] == visible_total - 1


def test_expired_jobs_are_neither_ranked_nor_counted(client, db):
    # AJI-028: the priority view scopes candidates through
    # job_listing_query, so a provider-stated expiry that has passed
    # removes the job exactly as it does from GET /jobs.
    user = make_user(db)
    version = make_resume(db, user)[0]
    open_job = make_job(
        db, expires_at=datetime.utcnow() + timedelta(days=1)
    )
    expired = make_job(db, expires_at=datetime.utcnow() - timedelta(days=1))
    make_job(db, expires_at=datetime.utcnow() - timedelta(days=1))
    analyze(db, user, open_job, version, match=60, ats=60)
    analyze(db, user, expired, version, match=99, ats=99)

    body = get_priority(client, user)
    listed = client.get("/jobs", headers=auth(user)).json()
    listed_ids = {job["id"] for job in listed["jobs"]}

    assert ids(body) == [str(open_job.id)]
    assert str(expired.id) not in listed_ids
    # Only the open analyzed job is ranked; the two expired jobs are not
    # counted as unanalyzed either - they are out of scope entirely.
    assert body["counts"]["unanalyzed"] == listed["pagination"]["total"] - 1


def test_newer_job_intelligence_marks_match_out_of_date(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db)
    analyze(db, user, job, version, match=77, ats=70)

    make_ji(db, job, created_at=datetime.now(timezone.utc) + timedelta(minutes=5))

    item = item_for(get_priority(client, user), job)

    assert item["state"] == "partial"
    assert item["inputs"]["job_match"]["current"] is False
    assert item["inputs"]["ats_alignment"]["current"] is False
    codes = [reason["code"] for reason in item["reasons"]]
    assert "job_match_outdated_job_intelligence" in codes
    assert "ats_outdated_job_intelligence" in codes
    # The stored score is still what orders it - flagged, not discarded.
    assert item["rank"] == 1
    assert item["inputs"]["job_match"]["score"] == 77


def test_legacy_match_without_job_intelligence(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db)
    make_match(db, user, job, version, 55, None)

    item = item_for(get_priority(client, user), job)

    assert item["state"] == "partial"
    assert item["inputs"]["job_match"]["job_intelligence_id"] is None
    assert "job_match_legacy_source" in [r["code"] for r in item["reasons"]]


def test_older_ats_engine_version_is_flagged(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db)
    ji = make_ji(db, job)
    ri = make_ri(db, user, job)
    make_match(db, user, job, version, 60, ji)
    make_ats(db, user, job, version, 60, ji, ri, engine="1.0.0")

    item = item_for(get_priority(client, user), job)

    assert item["state"] == "partial"
    assert "ats_outdated_engine" in [r["code"] for r in item["reasons"]]


def test_latest_result_per_job_is_used(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db)
    ji = make_ji(db, job)
    older = make_match(db, user, job, version, 20, ji)
    older.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    newer = make_match(db, user, job, version, 65, ji)
    db.flush()

    item = item_for(get_priority(client, user), job)

    assert item["inputs"]["job_match"]["id"] == str(newer.id)


# ---------------------------------------------------------------------------
# Resume versions
# ---------------------------------------------------------------------------


def test_resume_versions_never_mix(client, db):
    user = make_user(db)
    master, tailored = make_resume(db, user)
    job_a = make_job(db, title="A")
    job_b = make_job(db, title="B")

    ji_a, ji_b = make_ji(db, job_a), make_ji(db, job_b)
    ri_a, ri_b = make_ri(db, user, job_a), make_ri(db, user, job_b)

    make_match(db, user, job_a, master, 90, ji_a)
    make_ats(db, user, job_a, master, 90, ji_a, ri_a)
    make_match(db, user, job_b, master, 40, ji_b)

    make_match(db, user, job_a, tailored, 30, ji_a)
    tailored_b = make_match(db, user, job_b, tailored, 85, ji_b)
    tailored_ats_b = make_ats(db, user, job_b, tailored, 75, ji_b, ri_b)

    by_master = get_priority(client, user, resume_version_id=str(master.id))
    by_tailored = get_priority(client, user, resume_version_id=str(tailored.id))

    assert ids(by_master) == [str(job_a.id), str(job_b.id)]
    assert ids(by_tailored) == [str(job_b.id), str(job_a.id)]
    assert by_tailored["resume_version"]["id"] == str(tailored.id)

    b_tailored = item_for(by_tailored, job_b)
    assert b_tailored["inputs"]["job_match"]["id"] == str(tailored_b.id)
    assert b_tailored["inputs"]["ats_alignment"]["id"] == str(tailored_ats_b.id)

    # The master version's ATS for job A never appears under the tailored
    # version, where job A has no ATS result.
    assert item_for(by_tailored, job_a)["inputs"]["ats_alignment"] is None
    assert item_for(by_master, job_b)["inputs"]["ats_alignment"] is None


def test_default_resume_version_is_the_same_one_job_match_uses(client, db):
    user = make_user(db)
    master, tailored = make_resume(db, user)
    job = make_job(db)
    ji = make_ji(db, job)
    make_match(db, user, job, master, 70, ji)
    make_match(db, user, job, tailored, 20, ji)

    body = get_priority(client, user)

    assert body["resume_version"]["id"] == str(master.id)
    assert item_for(body, job)["inputs"]["job_match"]["score"] == 70


def test_no_resume_is_an_empty_result_not_an_error(client, db):
    user = make_user(db)
    make_job(db)

    body = get_priority(client, user)

    assert body["resume_version"] is None
    assert body["items"] == []
    assert body["counts"]["unanalyzed"] >= 1


@pytest.mark.parametrize("value", ["not-a-uuid", str(uuid4())])
def test_unknown_resume_version_is_404(client, db, value):
    user = make_user(db)
    make_resume(db, user)

    response = client.get(
        "/jobs/priority", headers=auth(user), params={"resume_version_id": value}
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# User isolation and private jobs
# ---------------------------------------------------------------------------


def test_one_users_analyses_never_rank_for_another(client, db):
    alice = make_user(db)
    bob = make_user(db)
    alice_version = make_resume(db, alice)[0]
    make_resume(db, bob)
    shared = make_job(db, title="Shared discovered job")
    alice_records = analyze(db, alice, shared, alice_version, match=95, ats=95)

    bob_body = get_priority(client, bob)

    assert item_for(bob_body, shared) is None
    serialized = str(bob_body)
    assert str(alice.id) not in serialized
    assert str(alice_version.id) not in serialized
    assert str(alice_records["match"].id) not in serialized
    assert str(alice_records["ats"].id) not in serialized


def test_rows_are_always_filtered_by_the_callers_user_id(client, db):
    # Resume versions are owned, so the version pin already isolates
    # users; the user_id filter is the second guard. A row that pairs
    # another user's id with the caller's version (impossible through the
    # API) must still never be read.
    alice = make_user(db)
    bob = make_user(db)
    bob_version = make_resume(db, bob)[0]
    job = make_job(db)
    ji = make_ji(db, job)
    make_match(db, alice, job, bob_version, 99, ji)

    assert item_for(get_priority(client, bob), job) is None


def test_another_users_resume_version_is_404(client, db):
    alice = make_user(db)
    bob = make_user(db)
    alice_version = make_resume(db, alice)[0]
    make_resume(db, bob)

    response = client.get(
        "/jobs/priority",
        headers=auth(bob),
        params={"resume_version_id": str(alice_version.id)},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Resume version not found."


def test_own_private_job_ranks_but_never_for_anyone_else(client, db):
    alice = make_user(db)
    bob = make_user(db)
    alice_version = make_resume(db, alice)[0]
    bob_version = make_resume(db, bob)[0]
    private = make_job(db, title="Alice private", submitted_by=alice)
    analyze(db, alice, private, alice_version, match=70, ats=70)

    # Defense in depth: even a stray Bob row for Alice's private job is
    # never ranked, listed, or counted for Bob.
    analyze(db, bob, private, bob_version, match=99, ats=99)

    alice_item = item_for(get_priority(client, alice), private)
    assert alice_item["job"]["origin"] == "user_submitted"
    assert alice_item["rank"] == 1

    bob_body = get_priority(client, bob)
    assert item_for(bob_body, private) is None
    assert "Alice private" not in str(bob_body)


def test_test_fixture_jobs_follow_test_mode(client, db, monkeypatch):
    user = make_user(db)
    version = make_resume(db, user)[0]
    fixture_job = make_job(db, title="Fixture", source=TEST_FIXTURE_SOURCE)
    analyze(db, user, fixture_job, version, match=80, ats=80)

    assert item_for(get_priority(client, user), fixture_job) is None

    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", True)

    item = item_for(get_priority(client, user), fixture_job)
    assert item["job"]["is_test_data"] is True


def test_inactive_jobs_are_not_ranked(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    closed = make_job(db, is_active=False)
    analyze(db, user, closed, version, match=90, ats=90)

    assert item_for(get_priority(client, user), closed) is None


# ---------------------------------------------------------------------------
# Job types, origins, filters, pagination
# ---------------------------------------------------------------------------


def test_full_time_and_contract_both_rank_and_filter(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    full_time = make_job(db, employment_type="full_time")
    contract = make_job(db, employment_type="contract")
    analyze(db, user, full_time, version, match=60, ats=60)
    analyze(db, user, contract, version, match=70, ats=70)

    both = get_priority(client, user)
    assert ids(both) == [str(contract.id), str(full_time.id)]

    only_contract = get_priority(client, user, employment_type="contract")
    assert ids(only_contract) == [str(contract.id)]
    assert only_contract["items"][0]["rank"] == 1
    assert only_contract["items"][0]["job"]["employment_type"] == "contract"


def test_discovered_and_submitted_jobs_rank_together(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    discovered = make_job(db, title="Discovered")
    submitted = make_job(db, title="Mine", submitted_by=user)
    analyze(db, user, discovered, version, match=50, ats=50)
    analyze(db, user, submitted, version, match=65, ats=65)

    body = get_priority(client, user)

    assert ids(body) == [str(submitted.id), str(discovered.id)]
    assert [item["job"]["origin"] for item in body["items"]] == [
        "user_submitted", "discovered",
    ]


def test_search_filter_is_the_listing_filter(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    wanted = make_job(db, title="Data Engineer")
    other = make_job(db, title="Designer")
    analyze(db, user, wanted, version, match=40, ats=40)
    analyze(db, user, other, version, match=90, ats=90)

    body = get_priority(client, user, search="data")

    assert ids(body) == [str(wanted.id)]
    assert body["counts"]["unanalyzed"] == 0


def test_pagination_keeps_global_ranks(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    jobs = [make_job(db, title=f"Job {n}") for n in range(3)]
    for score, job in zip((90, 80, 70), jobs):
        analyze(db, user, job, version, match=score, ats=score)

    second_page = get_priority(client, user, page=2, page_size=1)

    assert ids(second_page) == [str(jobs[1].id)]
    assert second_page["items"][0]["rank"] == 2
    assert second_page["pagination"] == {
        "page": 2, "page_size": 1, "total": 3, "total_pages": 3,
    }


def test_ranking_happens_before_pagination_not_per_page(client, db):
    # The listing order (newest first) is the reverse of priority order
    # here, so ranking each page separately would put the newest,
    # lowest-Match job first on page 1.
    user = make_user(db)
    version = make_resume(db, user)[0]
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    oldest_best = make_job(db, title="Best", posting_date=base)
    middle = make_job(db, title="Middle", posting_date=base + timedelta(days=1))
    newest_worst = make_job(db, title="Worst", posting_date=base + timedelta(days=2))
    analyze(db, user, oldest_best, version, match=90, ats=10)
    analyze(db, user, middle, version, match=60, ats=60)
    analyze(db, user, newest_worst, version, match=30, ats=99)

    pages = [get_priority(client, user, page=n, page_size=1) for n in (1, 2, 3)]

    assert [ids(p) for p in pages] == [
        [str(oldest_best.id)], [str(middle.id)], [str(newest_worst.id)],
    ]
    assert [p["items"][0]["rank"] for p in pages] == [1, 2, 3]


def test_same_inputs_return_the_same_order(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    for score in (70, 70, 70, 50):
        analyze(db, user, make_job(db), version, match=score, ats=40)

    first = get_priority(client, user)
    second = get_priority(client, user)

    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


# ---------------------------------------------------------------------------
# Read-only: no writes, no AI, no application changes
# ---------------------------------------------------------------------------


def _row_counts(db):
    models = [
        JobEligibilityResult, JobMatchResult, AtsAlignmentResult,
        JobIntelligence, RequirementIntelligence, GapAnalysis,
        SavedJob, ApplicationStatusEvent,
    ]
    return {m.__name__: db.scalar(select(func.count()).select_from(m)) for m in models}


def test_priority_is_read_only_and_never_calls_ai(client, db, monkeypatch):
    def _forbidden():  # pragma: no cover - must never run
        raise AssertionError("priority must not call an AI provider")

    monkeypatch.setattr(
        job_intelligence_service, "create_job_intelligence_provider", _forbidden
    )
    monkeypatch.setattr(
        requirement_intelligence_service,
        "create_requirement_intelligence_provider",
        _forbidden,
    )

    user = make_user(db, employment_types=["full_time"])
    version = make_resume(db, user)[0]
    analyzed = make_job(db)
    make_job(db)
    analyze(db, user, analyzed, version, match=60)

    before = _row_counts(db)
    get_priority(client, user)
    assert _row_counts(db) == before


def test_application_state_is_untouched_and_does_not_reorder(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    saved = make_job(db, title="Saved")
    applied = make_job(db, title="Applied")
    untracked = make_job(db, title="Untracked")
    analyze(db, user, saved, version, match=60, ats=60)
    analyze(db, user, applied, version, match=80, ats=80)
    analyze(db, user, untracked, version, match=70, ats=70)

    headers = auth(user)
    saved_id = client.post("/applications", json={"job_id": str(saved.id)}, headers=headers).json()["id"]
    applied_id = client.post("/applications", json={"job_id": str(applied.id)}, headers=headers).json()["id"]
    client.patch(f"/applications/{applied_id}", json={"status": "applied"}, headers=headers)

    body = get_priority(client, user)

    # Ordered purely by the evidence; tracking status has no effect.
    assert ids(body) == [str(applied.id), str(untracked.id), str(saved.id)]

    statuses = {
        app_row["id"]: app_row["status"]
        for app_row in client.get("/applications", headers=headers).json()
    }
    assert statuses == {saved_id: "saved", applied_id: "applied"}
    assert db.scalar(
        select(func.count()).select_from(SavedJob).where(SavedJob.user_id == user.id)
    ) == 2


@pytest.mark.parametrize(
    "status",
    ["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"],
)
def test_no_tracking_status_changes_the_order(client, db, status):
    # Documents the current behavior: tracking status is not a priority
    # input (no approved rule), so even a rejected or withdrawn job keeps
    # its place. Whether it should is an open Product Owner decision.
    user = make_user(db)
    version = make_resume(db, user)[0]
    tracked = make_job(db, title="Tracked")
    untracked = make_job(db, title="Untracked")
    analyze(db, user, tracked, version, match=90, ats=90)
    analyze(db, user, untracked, version, match=50, ats=50)
    before = get_priority(client, user)

    headers = auth(user)
    app_id = client.post(
        "/applications", json={"job_id": str(tracked.id)}, headers=headers
    ).json()["id"]
    client.patch(f"/applications/{app_id}", json={"status": status}, headers=headers)

    after = get_priority(client, user)

    assert ids(after) == ids(before) == [str(tracked.id), str(untracked.id)]
    assert item_for(after, tracked)["rank"] == 1
    assert item_for(after, tracked)["state"] == "ranked"


def test_public_listing_never_includes_priority(client, db):
    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db)
    analyze(db, user, job, version, match=80, ats=80)

    for headers in ({}, auth(user)):
        listing = client.get("/jobs", headers=headers).json()
        for payload in listing["jobs"]:
            for key in ("rank", "state", "reasons", "blocking_factors", "inputs", "priority"):
                assert key not in payload


# ---------------------------------------------------------------------------
# Performance: no N+1
# ---------------------------------------------------------------------------


def _count_queries(client, db, user):
    statements = []

    def _record(conn, cursor, statement, *args):
        statements.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", _record)
    try:
        db.expire_all()
        get_priority(client, user)
    finally:
        event.remove(connection, "before_cursor_execute", _record)

    return len(statements)


def test_query_count_does_not_grow_with_ranked_jobs(client, db):
    user = make_user(db, employment_types=["full_time"])
    version = make_resume(db, user)[0]

    first = make_job(db)
    analyze(db, user, first, version, match=50, ats=50)
    with_one = _count_queries(client, db, user)

    for score in (55, 60, 65, 70, 75, 80):
        analyze(db, user, make_job(db), version, match=score, ats=score)
    with_seven = _count_queries(client, db, user)

    assert with_one == with_seven


# ---------------------------------------------------------------------------
# End to end with the real Job Match and ATS Alignment services
# ---------------------------------------------------------------------------


class _UnavailableProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def generate_job_semantics(self, **_):
        raise RuntimeError("offline")

    def generate_requirement_semantics(self, **_):
        raise RuntimeError("offline")


def test_real_match_and_ats_results_are_what_priority_reads(client, db, monkeypatch):
    # Offline: AI stages degrade to their deterministic results.
    monkeypatch.setattr(
        job_intelligence_service,
        "create_job_intelligence_provider",
        lambda: _UnavailableProvider(),
    )
    monkeypatch.setattr(
        requirement_intelligence_service,
        "create_requirement_intelligence_provider",
        lambda: _UnavailableProvider(),
    )

    user = make_user(db)
    version = make_resume(db, user)[0]
    job = make_job(db, title="Python Engineer")
    headers = auth(user)

    match = client.post(f"/jobs/{job.id}/match", headers=headers).json()
    ats = client.post(f"/jobs/{job.id}/ats", headers=headers).json()

    item = item_for(get_priority(client, user, resume_version_id=str(version.id)), job)

    assert item["state"] == "ranked"
    assert item["inputs"]["job_match"]["id"] == match["id"]
    assert item["inputs"]["job_match"]["score"] == match["score"]
    assert item["inputs"]["ats_alignment"]["id"] == ats["id"]
    assert item["inputs"]["ats_alignment"]["overall_score"] == ats["overall_score"]
    assert item["inputs"]["job_match"]["current"] is True
    assert item["inputs"]["ats_alignment"]["current"] is True

    # Priority changed neither score: the job's own results read the same.
    assert client.get(f"/jobs/{job.id}/match", headers=headers).json()["score"] == match["score"]
    assert client.get(f"/jobs/{job.id}/ats", headers=headers).json()["overall_score"] == ats["overall_score"]
