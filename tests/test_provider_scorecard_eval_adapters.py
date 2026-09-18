from services.provider_scorecard.contracts import SearchScenario
from services.provider_scorecard.eval_adapters.adzuna import AdzunaEvalAdapter
from services.provider_scorecard.eval_adapters.jooble import JoobleEvalAdapter
from services.provider_scorecard.eval_adapters.the_muse import TheMuseEvalAdapter
from services.provider_scorecard.eval_adapters.usajobs import UsaJobsEvalAdapter

SCENARIO = SearchScenario(
    scenario_id="backend-remote",
    description="Backend engineer, remote",
    keywords="backend engineer",
    location="New York, NY",
    remote_preference="remote",
)


# ---------------------------------------------------------------------------
# from_env()
# ---------------------------------------------------------------------------


def test_adzuna_from_env_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    assert AdzunaEvalAdapter.from_env() is None


def test_adzuna_from_env_builds_adapter_when_configured(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id-123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key-456")

    adapter = AdzunaEvalAdapter.from_env()

    assert adapter is not None
    assert adapter.app_id == "id-123"
    assert adapter.country == "us"


def test_jooble_from_env_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("JOOBLE_API_KEY", raising=False)

    assert JoobleEvalAdapter.from_env() is None


def test_usajobs_from_env_requires_both_variables(monkeypatch):
    monkeypatch.setenv("USAJOBS_API_KEY", "key-123")
    monkeypatch.delenv("USAJOBS_USER_AGENT_EMAIL", raising=False)

    assert UsaJobsEvalAdapter.from_env() is None


def test_the_muse_from_env_is_always_configured(monkeypatch):
    monkeypatch.delenv("THE_MUSE_API_KEY", raising=False)

    adapter = TheMuseEvalAdapter.from_env()

    assert adapter is not None
    assert adapter.api_key is None


# ---------------------------------------------------------------------------
# Adzuna mapping
# ---------------------------------------------------------------------------

ADZUNA_FIXTURE = {
    "results": [
        {
            "id": 12345,
            "title": "Backend Engineer",
            "description": "Build backend systems.",
            "company": {"display_name": "Example Inc"},
            "location": {"display_name": "New York, NY"},
            "salary_min": 90000.0,
            "salary_max": 120000.0,
            "contract_time": "full_time",
            "contract_type": "permanent",
            "redirect_url": "https://www.adzuna.com/land/ad/12345",
            "created": "2024-01-15T10:00:00Z",
        }
    ],
    "count": 1,
}


def test_adzuna_maps_fixture_into_discovered_jobs(monkeypatch):
    adapter = AdzunaEvalAdapter(app_id="id", app_key="key")
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.adzuna.get_json",
        lambda url, timeout=15.0: ADZUNA_FIXTURE,
    )

    jobs = adapter.search(SCENARIO)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "adzuna"
    assert job.source_job_id == "12345"
    assert job.title == "Backend Engineer"
    assert job.company == "Example Inc"
    assert job.location == "New York, NY"
    assert job.country == "USA"
    assert job.employment_type == "full_time"
    assert job.salary_min == 90000.0
    assert job.salary_max == 120000.0
    assert job.source_url == "https://www.adzuna.com/land/ad/12345"
    assert job.posted_at is not None


def test_adzuna_non_us_country_is_upper_cased_not_guessed(monkeypatch):
    adapter = AdzunaEvalAdapter(app_id="id", app_key="key", country="gb")
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.adzuna.get_json",
        lambda url, timeout=15.0: ADZUNA_FIXTURE,
    )

    jobs = adapter.search(SCENARIO)

    assert jobs[0].country == "GB"


def test_adzuna_raises_on_unexpected_response_shape(monkeypatch):
    adapter = AdzunaEvalAdapter(app_id="id", app_key="key")
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.adzuna.get_json",
        lambda url, timeout=15.0: {"unexpected": "shape"},
    )

    try:
        adapter.search(SCENARIO)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# Jooble mapping
# ---------------------------------------------------------------------------

JOOBLE_FIXTURE = {
    "totalCount": 1,
    "jobs": [
        {
            "id": 987,
            "title": "Frontend Engineer",
            "location": "New York, NY",
            "snippet": "Build frontend UIs.",
            "salary": "$90,000 - $120,000",
            "type": "Full-time",
            "link": "https://jooble.org/desc/987",
            "company": "Example Inc",
            "updated": "2024-01-10T00:00:00Z",
        }
    ],
}


def test_jooble_maps_fixture_into_discovered_jobs(monkeypatch):
    adapter = JoobleEvalAdapter(api_key="key")
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.jooble.post_json",
        lambda url, payload, timeout=15.0: JOOBLE_FIXTURE,
    )

    jobs = adapter.search(SCENARIO)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "jooble"
    assert job.title == "Frontend Engineer"
    assert job.company == "Example Inc"
    assert job.country == "USA"
    # Unstructured salary text is dropped, not mis-parsed into a number.
    assert job.salary_min is None
    assert job.salary_max is None


def test_jooble_leaves_country_blank_for_non_us_location(monkeypatch):
    fixture = {
        "jobs": [
            {**JOOBLE_FIXTURE["jobs"][0], "location": "London, UK"},
        ]
    }
    adapter = JoobleEvalAdapter(api_key="key")
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.jooble.post_json",
        lambda url, payload, timeout=15.0: fixture,
    )

    jobs = adapter.search(SCENARIO)

    assert jobs[0].country == ""


# ---------------------------------------------------------------------------
# USAJOBS mapping
# ---------------------------------------------------------------------------

USAJOBS_FIXTURE = {
    "SearchResult": {
        "SearchResultCount": 1,
        "SearchResultItems": [
            {
                "MatchedObjectId": "700000012345",
                "MatchedObjectDescriptor": {
                    "PositionTitle": "IT Specialist",
                    "OrganizationName": "Department of Example",
                    "PositionLocationDisplay": "Washington, District of Columbia",
                    "PositionURI": "https://www.usajobs.gov/job/700000012345",
                    "ApplyURI": ["https://www.usajobs.gov/job/700000012345/apply"],
                    "PositionRemuneration": [
                        {
                            "MinimumRange": "80000.00",
                            "MaximumRange": "100000.00",
                            "RateIntervalCode": "Per Year",
                        }
                    ],
                    "PositionSchedule": [{"Name": "Full-time", "Code": "1"}],
                    "UserArea": {
                        "Details": {"JobSummary": "Serve as an IT Specialist."}
                    },
                    "PublicationStartDate": "2024-01-01",
                    "ApplicationCloseDate": "2024-02-01",
                },
            }
        ],
    }
}


def test_usajobs_maps_fixture_into_discovered_jobs(monkeypatch):
    adapter = UsaJobsEvalAdapter(api_key="key", user_agent_email="dev@example.com")
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.usajobs.get_json",
        lambda url, headers=None, timeout=15.0: USAJOBS_FIXTURE,
    )

    jobs = adapter.search(SCENARIO)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "usajobs"
    assert job.source_job_id == "700000012345"
    assert job.title == "IT Specialist"
    assert job.company == "Department of Example"
    assert job.country == "USA"
    assert job.employment_type == "Full-time"
    assert job.salary_min == 80000.0
    assert job.salary_max == 100000.0
    assert job.salary_currency == "USD"
    assert job.application_url == "https://www.usajobs.gov/job/700000012345/apply"
    assert job.posted_at is not None
    assert job.expires_at is not None


def test_usajobs_sends_authentication_headers(monkeypatch):
    captured = {}

    def fake_get_json(url, headers=None, timeout=15.0):
        captured["headers"] = headers
        return USAJOBS_FIXTURE

    adapter = UsaJobsEvalAdapter(api_key="secret-key", user_agent_email="dev@example.com")
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.usajobs.get_json", fake_get_json
    )

    adapter.search(SCENARIO)

    assert captured["headers"]["Authorization-Key"] == "secret-key"
    assert captured["headers"]["User-Agent"] == "dev@example.com"


# ---------------------------------------------------------------------------
# The Muse mapping
# ---------------------------------------------------------------------------

THE_MUSE_FIXTURE = {
    "results": [
        {
            "id": 555,
            "name": "Software Engineer",
            "contents": "<p>Build things.</p>",
            "company": {"name": "Example Inc"},
            "locations": [{"name": "New York, NY"}],
            "publication_date": "2024-01-05T00:00:00Z",
            "refs": {
                "landing_page": "https://www.themuse.com/jobs/example/software-engineer"
            },
        }
    ],
    "page_count": 1,
}


def test_the_muse_maps_fixture_into_discovered_jobs(monkeypatch):
    adapter = TheMuseEvalAdapter()
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.the_muse.get_json",
        lambda url, timeout=15.0: THE_MUSE_FIXTURE,
    )

    jobs = adapter.search(SCENARIO)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == "the_muse"
    assert job.title == "Software Engineer"
    assert job.company == "Example Inc"
    assert job.country == "USA"
    assert job.remote_type is None
    assert job.employment_type is None


def test_the_muse_detects_remote_location_but_flags_non_us_country():
    adapter = TheMuseEvalAdapter()
    raw = {
        "id": 999,
        "name": "Remote Engineer",
        "locations": [{"name": "Flexible / Remote"}],
    }

    job = adapter._to_discovered_job(raw)

    assert job.remote_type == "Remote"
    # "Flexible / Remote" has no U.S. marker - never guessed as USA.
    assert job.country == ""


def test_the_muse_never_sends_keywords_as_a_query_param(monkeypatch):
    captured = {}

    def fake_get_json(url, timeout=15.0):
        captured["url"] = url
        return THE_MUSE_FIXTURE

    adapter = TheMuseEvalAdapter()
    monkeypatch.setattr(
        "services.provider_scorecard.eval_adapters.the_muse.get_json", fake_get_json
    )

    adapter.search(SCENARIO)

    assert "keyword" not in captured["url"].lower()
