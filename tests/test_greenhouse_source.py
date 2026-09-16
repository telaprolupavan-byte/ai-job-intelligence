import json
import urllib.request
from datetime import datetime

import pytest

from services.job_discovery.sources.greenhouse import (
    GreenhouseAdapterError,
    GreenhouseJobSource,
)


SAMPLE_BOARD_RESPONSE = {
    "jobs": [
        {
            "id": 1001,
            "title": "Senior Machine Learning Engineer",
            "location": {"name": "New York, NY"},
            "content": "<p>Build <b>ML</b> systems.</p>",
            "absolute_url": "https://boards.greenhouse.io/example/jobs/1001",
            "updated_at": "2026-01-10T12:00:00-05:00",
            "metadata": [
                {"name": "Employment Type", "value": "Full-time"},
                {"name": "Remote", "value": "Hybrid"},
            ],
        },
        {
            "id": 1002,
            "title": "Platform Engineer",
            "location": {"name": "Berlin, Germany"},
            "content": "<p>Non-U.S. role.</p>",
            "absolute_url": "https://boards.greenhouse.io/example/jobs/1002",
            "updated_at": "2026-01-11T09:00:00-05:00",
            "metadata": [],
        },
        {
            "id": 1003,
            "title": "Support Engineer",
            "location": {"name": "Remote - USA"},
            "content": "<p>Fully remote role.</p>",
            "absolute_url": "https://boards.greenhouse.io/example/jobs/1003",
            "updated_at": None,
            "metadata": [],
        },
    ]
}


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_jobs_maps_greenhouse_payload(monkeypatch):
    def fake_urlopen(request, timeout=None):
        assert "example" in request.full_url
        return _FakeResponse(SAMPLE_BOARD_RESPONSE)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    source = GreenhouseJobSource(
        board_token="example",
        company_name="Example Inc",
    )

    jobs = source.fetch_jobs()

    assert len(jobs) == 3

    ny_job = jobs[0]
    assert ny_job.source == "greenhouse"
    assert ny_job.source_job_id == "1001"
    assert ny_job.title == "Senior Machine Learning Engineer"
    assert ny_job.company == "Example Inc"
    assert ny_job.country == "USA"
    assert ny_job.employment_type == "full_time"
    assert ny_job.remote_type == "hybrid"
    assert "ML systems" in (ny_job.description or "")
    assert "<" not in (ny_job.description or "")
    assert ny_job.source_url == "https://boards.greenhouse.io/example/jobs/1001"
    assert ny_job.application_url == ny_job.source_url
    assert ny_job.posted_at == datetime.fromisoformat("2026-01-10T12:00:00-05:00")
    assert ny_job.salary_min is None
    assert ny_job.salary_max is None


def test_non_us_location_is_not_marked_as_us(monkeypatch):
    def fake_urlopen(request, timeout=None):
        return _FakeResponse(SAMPLE_BOARD_RESPONSE)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    source = GreenhouseJobSource(board_token="example", company_name="Example Inc")
    jobs = source.fetch_jobs()

    berlin_job = next(job for job in jobs if job.source_job_id == "1002")

    assert berlin_job.country == ""


def test_remote_usa_location_is_marked_as_us(monkeypatch):
    def fake_urlopen(request, timeout=None):
        return _FakeResponse(SAMPLE_BOARD_RESPONSE)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    source = GreenhouseJobSource(board_token="example", company_name="Example Inc")
    jobs = source.fetch_jobs()

    remote_job = next(job for job in jobs if job.source_job_id == "1003")

    assert remote_job.country == "USA"
    assert remote_job.posted_at is None


def test_invalid_json_response_raises_adapter_error(monkeypatch):
    class _BadResponse:
        def read(self):
            return b"not json"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda request, timeout=None: _BadResponse()
    )

    source = GreenhouseJobSource(board_token="example", company_name="Example Inc")

    with pytest.raises(GreenhouseAdapterError):
        source.fetch_jobs()


def test_missing_board_token_raises_value_error():
    with pytest.raises(ValueError):
        GreenhouseJobSource(board_token="", company_name="Example Inc")
