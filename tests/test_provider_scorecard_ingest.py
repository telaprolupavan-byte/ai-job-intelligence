import json

import pytest

from services.provider_scorecard.ingest import build_reports_from_bundle, main


def test_build_reports_from_bundle_parses_multiple_providers():
    bundle = {
        "meta": {"greenhouse_company_name": "Example Inc"},
        "greenhouse": {
            "backend-remote": {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Backend Engineer",
                        "location": {"name": "New York, NY"},
                        "content": "<p>Build things.</p>",
                        "absolute_url": "https://boards.greenhouse.io/example/jobs/1",
                        "updated_at": "2024-01-15T00:00:00Z",
                        "metadata": [{"name": "Employment Type", "value": "Full-time"}],
                    }
                ]
            }
        },
        "the_muse": {
            "backend-remote": {
                "results": [
                    {
                        "id": 555,
                        "name": "Machine Learning Engineer",
                        "contents": "<p>Build models.</p>",
                        "company": {"name": "Example Inc"},
                        "locations": [{"name": "New York, NY"}],
                        "publication_date": "2024-01-05T00:00:00Z",
                        "refs": {"landing_page": "https://www.themuse.com/jobs/example/mle"},
                    }
                ]
            }
        },
    }

    reports = build_reports_from_bundle(bundle)

    providers = {report.provider for report in reports}
    assert providers == {"greenhouse", "the_muse"}

    the_muse_report = next(r for r in reports if r.provider == "the_muse")
    assert the_muse_report.raw_jobs == 1
    assert the_muse_report.ai_ml_jobs == 1


def test_build_reports_from_bundle_records_error_scenarios():
    bundle = {
        "the_muse": {
            "backend-remote": {"_error": "HTTP 500 Internal Server Error"},
        }
    }

    reports = build_reports_from_bundle(bundle)

    assert len(reports) == 1
    report = reports[0]
    assert report.provider == "the_muse"
    assert report.total_scenarios == 1
    assert report.successful_scenarios == 0
    assert report.reliability_rate == 0.0
    assert report.scenario_errors == {"backend-remote": "HTTP 500 Internal Server Error"}


def test_build_reports_from_bundle_greenhouse_requires_company_name():
    bundle = {
        "greenhouse": {
            "backend-remote": {"jobs": []},
        }
    }

    with pytest.raises(ValueError):
        build_reports_from_bundle(bundle)


def test_build_reports_from_bundle_skips_absent_providers():
    reports = build_reports_from_bundle({"adzuna": {}})

    assert reports == []


def test_main_reads_bundle_file_and_prints_table(tmp_path, capsys):
    bundle = {
        "the_muse": {
            "backend-remote": {
                "results": [
                    {
                        "id": 1,
                        "name": "Backend Engineer",
                        "company": {"name": "Example Inc"},
                        "locations": [{"name": "New York, NY"}],
                        "refs": {"landing_page": "https://www.themuse.com/jobs/example/1"},
                    }
                ]
            }
        }
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle))

    exit_code = main([str(bundle_path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "the_muse" in captured.out
    assert "Raw jobs" in captured.out


def test_main_returns_nonzero_when_bundle_has_no_provider_entries(tmp_path, capsys):
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps({}))

    exit_code = main([str(bundle_path)])

    assert exit_code == 1
