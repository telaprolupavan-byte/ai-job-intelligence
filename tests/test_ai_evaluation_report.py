"""AJI-031: runner, report formatting, regression comparison and CLI."""

import copy
import json
from pathlib import Path

import pytest

from services.ai_evaluation import run_eval, runner
from services.ai_evaluation.dataset import load_dataset
from services.ai_evaluation.report import (
    compare_reports,
    render_comparison,
    render_markdown,
)
from services.ai_evaluation.runner import run_evaluation


BASELINE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "ai_evaluation"
    / "baselines"
    / "v1-deterministic.json"
)


@pytest.fixture(scope="module")
def report():
    return run_evaluation(load_dataset())


def test_deterministic_run_covers_every_capability(report):
    names = [item["capability"] for item in report["capabilities"]]

    assert names == [
        "resume_intelligence_deterministic",
        "job_intelligence",
        "requirement_intelligence",
        "job_match",
        "gap_analysis",
        "general_resume_score",
    ]
    assert report["run"]["live_ai"] == {
        "requested": False,
        "ran": False,
        "reason": "Not requested (run with --live).",
    }
    assert report["dataset"]["version"] == "1.0.0"


def test_report_is_json_serializable(report):
    assert json.loads(json.dumps(report))["ticket"] == "AJI-031"


def test_markdown_lists_metrics_findings_and_live_status(report):
    markdown = render_markdown(report)

    assert "# NERO AI Evaluation Report (AJI-031)" in markdown
    assert "| Live AI evaluation | NOT RUN" in markdown
    assert "## Resume <-> Job Match" in markdown
    assert "| alternative_or_group_correctness |" in markdown
    assert "**Prompt-injection findings**" in markdown


def test_live_requested_without_providers_is_recorded_as_not_run(monkeypatch):
    def unavailable():
        raise RuntimeError("OpenAI API key is not configured.")

    monkeypatch.setattr(runner, "create_live_providers", unavailable)

    result = run_evaluation(load_dataset(), live=True)

    assert result["run"]["live_ai"]["ran"] is False
    assert "API key is not configured" in result["run"]["live_ai"]["reason"]
    assert all(item["mode"] == "deterministic" for item in result["capabilities"])


class _CannedProvider:
    """Stands in for a provider to test the live plumbing end to end. Its
    output is a fixed test input, not a measurement of any AI."""

    provider_name = "canned-test-provider"
    model_name = "none"

    def generate_structured_analysis(self, *, resume_text, deterministic_analysis):
        return {
            "review": {"strengths": [], "weaknesses": [], "findings": [], "suggestions": []},
            "decoding": {"skills": [], "work_history": [], "education": [],
                         "certifications": [], "projects": [], "domains": []},
            "position_identification": {"primary_roles": [], "secondary_roles": [],
                                        "adjacent_roles": [], "supporting_evidence": []},
        }

    def generate_job_semantics(self, *, raw_jd_text, deterministic_context):
        return {"domain": "Payments", "domain_evidence": "payment infrastructure"}

    def generate_requirement_semantics(self, *, raw_jd_text, deterministic_context):
        return {}


def test_live_plumbing_runs_through_production_interpreters_and_validators():
    provider = _CannedProvider()
    result = run_evaluation(
        load_dataset(),
        live=True,
        providers={"resume": provider, "job": provider, "requirement": provider},
    )
    live = [item for item in result["capabilities"] if item["mode"] == "live"]

    assert result["run"]["live_ai"]["ran"] is True
    assert [item["capability"] for item in live] == [
        "resume_intelligence_live",
        "job_intelligence_live",
        "requirement_intelligence_live",
    ]
    assert all(item["cases_errored"] == 0 for item in live)
    job_live = live[1]
    assert job_live["metrics"]["ai_evidence_grounding_rate"]["value"] == round(1 / 6, 4)


def _with_metric(report, capability, metric, value):
    changed = copy.deepcopy(report)
    target = next(c for c in changed["capabilities"] if c["capability"] == capability)
    target["metrics"][metric]["value"] = value
    return changed


def test_compare_flags_a_drop_in_a_higher_is_better_metric(report):
    worse = _with_metric(report, "job_match", "ranking_correctness", 0.2)

    comparison = compare_reports(report, worse)

    assert [item["metric"] for item in comparison["regressions"]] == [
        "job_match.ranking_correctness"
    ]
    assert comparison["improvements"] == []


def test_compare_flags_a_rise_in_a_lower_is_better_metric(report):
    worse = _with_metric(report, "job_match", "injected_skills_credited", 99)

    comparison = compare_reports(report, worse)

    assert [item["metric"] for item in comparison["regressions"]] == [
        "job_match.injected_skills_credited"
    ]


def test_compare_respects_tolerance_and_reports_improvements(report):
    metric = next(
        c for c in report["capabilities"] if c["capability"] == "job_match"
    )["metrics"]["required_gap_precision"]["value"]
    better = _with_metric(report, "job_match", "required_gap_precision", metric + 0.05)
    slightly_worse = _with_metric(report, "job_match", "required_gap_precision", metric - 0.01)

    assert compare_reports(report, better)["improvements"]
    assert compare_reports(report, slightly_worse, tolerance=0.02)["regressions"] == []


def test_compare_reports_cases_that_start_failing(report):
    worse = copy.deepcopy(report)
    general = next(c for c in worse["capabilities"] if c["capability"] == "general_resume_score")
    general["cases"][0]["passed"] = False

    comparison = compare_reports(report, worse)

    assert comparison["case_regressions"] == ["general_resume_score.R1"]
    assert "Cases that now fail: 1" in render_comparison(comparison)


def test_current_run_has_no_regressions_against_committed_baseline(report):
    baseline = json.loads(BASELINE.read_text())

    comparison = compare_reports(baseline, report)

    assert comparison["dataset_version_changed"] is False
    assert comparison["regressions"] == []
    assert comparison["case_regressions"] == []
    assert comparison["metrics_only_in_baseline"] == []


def test_cli_writes_reports_and_compares(tmp_path):
    code = run_eval.main(["--output-dir", str(tmp_path), "--compare", str(BASELINE),
                          "--fail-on-regression"])

    assert code == 0
    assert "## Comparison with baseline" in (tmp_path / "report.md").read_text()
    assert json.loads((tmp_path / "report.json").read_text())["comparison"]["regressions"] == []


def test_cli_live_without_providers_exits_2(tmp_path, monkeypatch):
    def unavailable():
        raise RuntimeError("no key")

    monkeypatch.setattr(runner, "create_live_providers", unavailable)

    assert run_eval.main(["--live", "--output-dir", str(tmp_path)]) == 2
    assert "NOT RUN" in (tmp_path / "report.md").read_text()
