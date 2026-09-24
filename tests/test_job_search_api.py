"""AJI-023 (Job Search): the search/discovery contract over HTTP, against a
real DB - valid and invalid criteria, empty results, the normalized job
shape (optional fields stay null), duplicates, job detail retrieval,
authentication, and predictable failure.

The listing query itself predates this ticket (tests/test_jobs_api.py);
these tests pin what AJI-023 adds on top of it."""

from typing import get_args
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Company, Job, User
from apps.api.security import create_access_token
from apps.api.services.job_discovery_service import run_configured_discovery
from apps.api.services.job_listing import (
    SEARCH_TEXT_MAX_LENGTH,
    EmploymentTypeFilter,
    RemoteTypeFilter,
    clean_search_text,
)
from services.job_discovery.normalizer import (
    EMPLOYMENT_TYPE_ALIASES,
    REMOTE_TYPE_ALIASES,
)
from services.job_discovery.sources.test_fixture import TEST_FIXTURE_SOURCE


JOB_KEYS = {
    "id",
    "title",
    "company",
    "location",
    "country",
    "remote_type",
    "employment_type",
    "salary_min",
    "salary_max",
    "salary_currency",
    "contract_duration",
    "contract_worker_type",
    "description",
    "requirements",
    "responsibilities",
    "posting_date",
    # AJI-028: provider-stated expiry and generic source attribution.
    "expires_at",
    "source",
    "source_attribution",
    "source_job_id",
    "origin",
    "is_test_data",
    "source_url",
    "application_url",
    "first_seen_at",
    "last_seen_at",
}


@pytest.fixture(autouse=True)
def _discovery_settings(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_greenhouse_board_token", None)
    monkeypatch.setattr(settings, "job_discovery_greenhouse_company_name", None)
    monkeypatch.setattr(settings, "job_discovery_provider", None)
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", False)


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"search-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _make_job(db, *, title, company="Initech", **fields) -> Job:
    suffix = uuid4().hex
    company_row = Company(
        name=f"{company} {suffix}", normalized_name=f"{company.lower()} {suffix}"
    )
    db.add(company_row)
    db.flush()

    values = {
        "company_id": company_row.id,
        "title": title,
        "country": "USA",
        "description": f"{title} role description with enough detail.",
        "source": "greenhouse",
        "is_active": True,
    }
    values.update(fields)

    job = Job(**values)
    db.add(job)
    db.flush()
    return job


def _token() -> str:
    """A title fragment no other row in the database can contain."""
    return f"zq{uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# Valid search + response structure
# ---------------------------------------------------------------------------


def test_valid_search_returns_the_normalized_contract(client, db):
    token = _token()
    job = _make_job(
        db,
        title=f"Platform Engineer {token}",
        location="Austin, TX",
        remote_type="hybrid",
        employment_type="full_time",
        salary_min=120000,
        salary_max=150000,
        salary_currency="USD",
        source_url="https://boards.example/jobs/42",
        application_url="https://boards.example/jobs/42/apply",
        external_job_id="42",
    )

    response = client.get("/jobs", params={"search": token})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"jobs", "pagination"}
    assert body["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 1,
        "total_pages": 1,
    }

    [result] = body["jobs"]
    assert set(result) == JOB_KEYS
    assert result["id"] == str(job.id)
    assert result["source"] == "greenhouse"
    assert result["source_job_id"] == "42"
    assert result["origin"] == "discovered"
    assert result["employment_type"] == "full_time"
    assert result["remote_type"] == "hybrid"
    assert result["salary_currency"] == "USD"


def test_search_is_case_insensitive_and_combines_criteria(client, db):
    token = _token()
    wanted = _make_job(
        db,
        title=f"Data Engineer {token}",
        employment_type="contract",
        remote_type="remote",
        location="Remote, United States",
    )
    _make_job(
        db,
        title=f"Data Engineer {token}",
        employment_type="full_time",
        remote_type="remote",
        location="Remote, United States",
    )
    _make_job(
        db,
        title=f"Data Engineer {token}",
        employment_type="contract",
        remote_type="onsite",
        location="Boston, MA",
    )

    response = client.get(
        "/jobs",
        params={
            "search": token.upper(),
            "employment_type": "contract",
            "remote_type": "remote",
            "location": "united states",
        },
    )

    assert response.status_code == 200
    assert [job["id"] for job in response.json()["jobs"]] == [str(wanted.id)]


def test_search_matches_company_name(client, db):
    token = _token()
    job = _make_job(db, title="Analyst", company=f"Acme {token}")

    response = client.get("/jobs", params={"search": token})

    assert [row["id"] for row in response.json()["jobs"]] == [str(job.id)]


def test_blank_criteria_are_ignored_not_matched_literally(client, db):
    token = _token()
    _make_job(db, title=f"Engineer {token}")

    unfiltered = client.get("/jobs").json()["pagination"]["total"]
    blank = client.get(
        "/jobs", params={"search": "   ", "location": "\t"}
    )

    assert blank.status_code == 200
    assert blank.json()["pagination"]["total"] == unfiltered


def test_search_text_is_trimmed_and_whitespace_collapsed(client, db):
    token = _token()
    job = _make_job(db, title=f"Senior Engineer {token}")

    response = client.get(
        "/jobs", params={"search": f"  senior   engineer {token}  "}
    )

    assert [row["id"] for row in response.json()["jobs"]] == [str(job.id)]


def test_wildcard_characters_are_searched_literally(client, db):
    token = _token()
    literal = _make_job(db, title=f"100% Remote Engineer {token}")
    _make_job(db, title=f"1000 Remote Engineer {token}")

    percent = client.get("/jobs", params={"search": f"100% remote engineer {token}"})
    underscore = client.get("/jobs", params={"search": f"{token}_"})

    assert [row["id"] for row in percent.json()["jobs"]] == [str(literal.id)]
    assert underscore.json()["jobs"] == []


def test_clean_search_text():
    assert clean_search_text(None) is None
    assert clean_search_text("   ") is None
    assert clean_search_text("  New   York ") == "New York"


# ---------------------------------------------------------------------------
# Invalid search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"employment_type": "fulltime"},
        {"employment_type": "Full-Time"},
        {"employment_type": ""},
        {"remote_type": "anywhere"},
        {"remote_type": "on-site"},
        {"search": "x" * (SEARCH_TEXT_MAX_LENGTH + 1)},
        {"location": "x" * (SEARCH_TEXT_MAX_LENGTH + 1)},
        {"page": 0},
        {"page": "abc"},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_invalid_criteria_are_rejected_with_422(client, params):
    response = client.get("/jobs", params=params)

    assert response.status_code == 422
    # FastAPI's structured validation detail names the offending param.
    [error] = response.json()["detail"]
    assert error["loc"][-1] == next(iter(params))


def test_search_at_the_length_limit_is_accepted(client):
    response = client.get(
        "/jobs", params={"search": "x" * SEARCH_TEXT_MAX_LENGTH}
    )

    assert response.status_code == 200


def test_priority_view_applies_the_same_validation(client, db):
    user = _make_user(db)

    response = client.get(
        "/jobs/priority",
        params={"remote_type": "anywhere"},
        headers=_auth(user),
    )

    assert response.status_code == 422


def test_filter_vocabularies_match_what_normalization_can_store():
    """A filter value the normalizer can never produce could only ever
    return zero jobs; a stored value missing here could never be found."""
    assert set(get_args(EmploymentTypeFilter)) == set(
        EMPLOYMENT_TYPE_ALIASES.values()
    )
    assert set(get_args(RemoteTypeFilter)) == set(REMOTE_TYPE_ALIASES.values())


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


def test_no_matches_is_an_empty_200_not_an_error(client):
    response = client.get("/jobs", params={"search": _token()})

    assert response.status_code == 200
    assert response.json() == {
        "jobs": [],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total": 0,
            "total_pages": 0,
        },
    }


def test_page_past_the_end_is_empty_not_an_error(client, db):
    token = _token()
    _make_job(db, title=f"Engineer {token}")

    response = client.get("/jobs", params={"search": token, "page": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["jobs"] == []
    assert body["pagination"]["total"] == 1


# ---------------------------------------------------------------------------
# Missing optional fields stay unknown
# ---------------------------------------------------------------------------


def test_missing_optional_fields_are_null_never_fabricated(client, db):
    token = _token()
    user = _make_user(db)
    job = _make_job(db, title=f"Minimal Posting {token}")

    listed = client.get("/jobs", params={"search": token}).json()["jobs"][0]
    detail = client.get(f"/jobs/{job.id}", headers=_auth(user)).json()

    for payload in (listed, detail):
        for field in (
            "location",
            "remote_type",
            "employment_type",
            "salary_min",
            "salary_max",
            "salary_currency",
            "contract_duration",
            "contract_worker_type",
            "requirements",
            "responsibilities",
            "posting_date",
            "source_job_id",
            "source_url",
            "application_url",
        ):
            assert payload[field] is None, field


def test_job_without_company_reports_null_company(client, db):
    token = _token()
    job = Job(
        title=f"Orphan Posting {token}",
        country="USA",
        description="A posting whose company row is gone.",
        source="greenhouse",
        is_active=True,
    )
    db.add(job)
    db.flush()

    [listed] = client.get("/jobs", params={"search": token}).json()["jobs"]

    assert listed["company"] is None


# ---------------------------------------------------------------------------
# Duplicates (through the real discovery pipeline)
# ---------------------------------------------------------------------------


def _run_discovery_as_separate_request(db):
    session = Session(
        bind=db.connection(), join_transaction_mode="create_savepoint"
    )
    try:
        return run_configured_discovery(session)
    finally:
        session.close()


def test_duplicate_postings_appear_once_in_search(client, db, monkeypatch):
    """The fixture batch repeats record fx-1001, and discovery then runs a
    second time: search must still show that posting exactly once."""
    monkeypatch.setattr(settings, "job_discovery_provider", "test_fixture")
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", True)

    first = _run_discovery_as_separate_request(db)
    second = _run_discovery_as_separate_request(db)

    assert first.duplicates == 1
    assert second.inserted == 0

    response = client.get(
        "/jobs",
        params={"search": "Senior Backend Engineer", "page_size": 100},
    )
    matches = [
        job
        for job in response.json()["jobs"]
        if job["source"] == TEST_FIXTURE_SOURCE
    ]

    assert len(matches) == 1
    assert matches[0]["source_job_id"] == "fx-1001"
    assert matches[0]["is_test_data"] is True

    all_ids = [
        job["id"]
        for job in client.get("/jobs", params={"page_size": 100}).json()["jobs"]
    ]
    assert len(all_ids) == len(set(all_ids))


# ---------------------------------------------------------------------------
# Job detail retrieval
# ---------------------------------------------------------------------------


def test_job_detail_returns_every_available_field(client, db):
    user = _make_user(db)
    job = _make_job(
        db,
        title="Staff Engineer",
        location="Denver, CO",
        remote_type="onsite",
        employment_type="contract",
        contract_duration="12 months",
        requirements="Go\nKubernetes",
        responsibilities="Own the platform",
        external_job_id="gh-7",
        source_url="https://boards.example/jobs/7",
    )

    response = client.get(f"/jobs/{job.id}", headers=_auth(user))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == JOB_KEYS | {"raw_submitted_content"}
    assert body["title"] == "Staff Engineer"
    assert body["requirements"] == "Go\nKubernetes"
    assert body["responsibilities"] == "Own the platform"
    assert body["contract_duration"] == "12 months"
    assert body["source_job_id"] == "gh-7"


@pytest.mark.parametrize("job_id", [str(uuid4()), "not-a-uuid"])
def test_missing_job_detail_is_404(client, db, job_id):
    user = _make_user(db)

    response = client.get(f"/jobs/{job_id}", headers=_auth(user))

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_inactive_job_is_not_searchable(client, db):
    token = _token()
    _make_job(db, title=f"Closed Role {token}", is_active=False)

    assert client.get("/jobs", params={"search": token}).json()["jobs"] == []


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_job_detail_requires_authentication(client, db):
    job = _make_job(db, title="Engineer")

    assert client.get(f"/jobs/{job.id}").status_code == 401
    assert (
        client.get(
            f"/jobs/{job.id}",
            headers={"Authorization": "Bearer not-a-real-token"},
        ).status_code
        == 401
    )


def test_priority_view_requires_authentication(client):
    assert client.get("/jobs/priority").status_code == 401


def test_anonymous_search_never_includes_private_submissions(client, db):
    token = _token()
    owner = _make_user(db)
    _make_job(
        db,
        title=f"Private Paste {token}",
        source="user_submitted",
        submitted_by_user_id=owner.id,
    )

    anonymous = client.get("/jobs", params={"search": token}).json()
    as_owner = client.get(
        "/jobs", params={"search": token}, headers=_auth(owner)
    ).json()
    as_stranger = client.get(
        "/jobs", params={"search": token}, headers=_auth(_make_user(db))
    ).json()

    assert anonymous["jobs"] == []
    assert as_stranger["jobs"] == []
    assert [job["origin"] for job in as_owner["jobs"]] == ["user_submitted"]


# ---------------------------------------------------------------------------
# Backend failure
# ---------------------------------------------------------------------------


def test_database_failure_is_a_plain_500_without_internals(db):
    class BrokenSession:
        def scalar(self, *args, **kwargs):
            raise OperationalError(
                "SELECT secret_table", {}, Exception("connection refused")
            )

        execute = scalar

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db

    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/jobs", params={"search": "engineer"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert "secret_table" not in response.text
    assert "connection refused" not in response.text
