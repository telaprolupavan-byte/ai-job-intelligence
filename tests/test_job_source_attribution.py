"""AJI-028 - generic source attribution: the registry's rules and the
`source_attribution` the Jobs API returns for every job.

No real provider requires attribution today, so link-back behavior is
exercised with a synthetic source registered only for the duration of a
test (monkeypatch) - the registry itself ships with no such entry.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.main import app
from apps.api.models import Company, Job, User
from apps.api.security import create_access_token
from services.job_discovery import attribution as attribution_module
from services.job_discovery.attribution import (
    SOURCE_ATTRIBUTIONS,
    SourceAttribution,
    _registry,
    attribution_link,
    get_source_attribution,
)
from services.job_discovery.sources.test_fixture import TEST_FIXTURE_SOURCE


CREDITED = SourceAttribution(
    source="credited_example",
    display_name="Credited Example",
    homepage_url="https://credited.example",
    requires_link_back=True,
)


# ---------------------------------------------------------------------------
# Registry rules
# ---------------------------------------------------------------------------


def test_registry_ships_without_any_link_back_source():
    # AJI-028 is foundation only: no provider whose terms require a link
    # back is registered (or enabled).
    assert all(not entry.requires_link_back for entry in SOURCE_ATTRIBUTIONS.values())


def test_greenhouse_keeps_its_existing_display_name():
    entry = get_source_attribution("greenhouse")

    assert entry is not None
    assert entry.display_name == "Greenhouse"
    assert entry.requires_link_back is False


@pytest.mark.parametrize("source", [None, "", "unknown_source", TEST_FIXTURE_SOURCE])
def test_unregistered_sources_have_no_attribution(source):
    assert get_source_attribution(source) is None


def test_lookup_can_use_an_explicit_registry():
    registry = _registry(CREDITED)

    assert get_source_attribution("credited_example", registry=registry) is CREDITED
    assert get_source_attribution("greenhouse", registry=registry) is None


def test_duplicate_registrations_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        _registry(CREDITED, CREDITED)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source": " ", "display_name": "X"},
        {"source": "x", "display_name": ""},
        {"source": "x", "display_name": "X", "homepage_url": "javascript:alert(1)"},
        {"source": "x", "display_name": "X", "homepage_url": "/relative"},
        # A link-back source must have somewhere to link when a posting
        # has no URL of its own.
        {"source": "x", "display_name": "X", "requires_link_back": True},
    ],
)
def test_invalid_attributions_are_rejected(kwargs):
    with pytest.raises(ValueError):
        SourceAttribution(**kwargs)


def test_link_prefers_the_posting_and_falls_back_to_the_homepage():
    assert (
        attribution_link(CREDITED, source_url="https://credited.example/jobs/7")
        == "https://credited.example/jobs/7"
    )
    assert attribution_link(CREDITED, source_url=None) == "https://credited.example"
    # An unsafe stored URL is never used as the link.
    assert (
        attribution_link(CREDITED, source_url="javascript:alert(1)")
        == "https://credited.example"
    )


# ---------------------------------------------------------------------------
# API: source_attribution on job responses
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _discovery_settings(monkeypatch):
    monkeypatch.setattr(settings, "job_discovery_provider", None)
    monkeypatch.setattr(settings, "job_discovery_enable_test_provider", True)


@pytest.fixture
def credited_source(monkeypatch):
    monkeypatch.setitem(
        attribution_module.SOURCE_ATTRIBUTIONS, CREDITED.source, CREDITED
    )


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"attribution-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _job(db, *, source: str, source_url=None, submitted_by=None) -> Job:
    company = Company(name="Attribution Co", normalized_name="attribution co")
    db.add(company)
    db.flush()
    job = Job(
        company_id=company.id,
        title="Platform Engineer",
        country="USA",
        description="Platform engineering role with enough detail.",
        source=source,
        source_url=source_url,
        is_active=True,
        submitted_by_user_id=submitted_by.id if submitted_by else None,
    )
    db.add(job)
    db.flush()
    return job


def _attribution(client, user, job):
    response = client.get(f"/jobs/{job.id}", headers=_auth(user))
    assert response.status_code == 200
    return response.json()["source_attribution"]


def test_link_back_source_gets_its_posting_link(client, db, credited_source):
    user = _user(db)
    job = _job(db, source=CREDITED.source, source_url="https://credited.example/jobs/9")

    assert _attribution(client, user, job) == {
        "name": "Credited Example",
        "url": "https://credited.example/jobs/9",
        "requires_link_back": True,
    }


def test_link_back_source_without_a_posting_url_links_home(client, db, credited_source):
    user = _user(db)
    job = _job(db, source=CREDITED.source)

    assert _attribution(client, user, job)["url"] == "https://credited.example"


def test_greenhouse_attribution_is_name_only(client, db):
    user = _user(db)
    job = _job(db, source="greenhouse", source_url="https://boards.greenhouse.io/x/jobs/1")

    assert _attribution(client, user, job) == {
        "name": "Greenhouse",
        "url": "https://boards.greenhouse.io/x/jobs/1",
        "requires_link_back": False,
    }


def test_test_fixture_and_unknown_sources_have_none(client, db):
    user = _user(db)

    assert _attribution(client, user, _job(db, source=TEST_FIXTURE_SOURCE)) is None
    assert _attribution(client, user, _job(db, source="unregistered")) is None


def test_user_submitted_jobs_never_carry_attribution(client, db, credited_source):
    user = _user(db)
    # Even if a submission's source string matched a registered source,
    # a user's own job is never credited to a provider.
    job = _job(db, source=CREDITED.source, submitted_by=user)

    assert _attribution(client, user, job) is None


def test_listing_items_carry_attribution(client, db, credited_source):
    user = _user(db)
    job = _job(db, source=CREDITED.source, source_url="https://credited.example/jobs/3")

    listing = client.get(
        "/jobs", params={"search": "Platform Engineer"}, headers=_auth(user)
    ).json()["jobs"]

    item = next(j for j in listing if j["id"] == str(job.id))
    assert item["source_attribution"]["name"] == "Credited Example"
