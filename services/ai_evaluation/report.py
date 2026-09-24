"""Report rendering and regression comparison for AJI-031.

`render_markdown` turns a report dict (from `runner.run_evaluation`)
into a readable Markdown document. `compare_reports` compares two
reports metric by metric, using each metric's own `direction`, and also
lists cases that passed before and fail now, so a later run can be
checked against the committed baseline.
"""

from __future__ import annotations


CATEGORY_LABELS = {
    "unsupported_claim": "Unsupported claims",
    "extraction_error": "Extraction errors",
    "matching_error": "Matching errors",
    "requirement_interpretation_error": "Requirement interpretation errors",
    "grounding_failure": "Grounding failures",
    "prompt_injection": "Prompt-injection findings",
    "human_review": "Needs human review",
    "error": "Pipeline errors",
}


def _format_value(metric: dict) -> str:
    value = metric.get("value")

    if value is None:
        text = "n/a"
    elif isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
    else:
        text = str(value)

    if "denominator" in metric:
        text += f" ({metric['numerator']}/{metric['denominator']})"

    return text


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    run = report["run"]
    dataset = report["dataset"]
    live = run["live_ai"]
    lines = [
        "# NERO AI Evaluation Report (AJI-031)",
        "",
        "| | |",
        "|---|---|",
        f"| Dataset | {dataset['name']} v{dataset['version']} (synthetic: {dataset['synthetic']}) |",
        f"| Cases | {dataset['resumes']} resumes, {dataset['jobs']} jobs, "
        f"{dataset['match_cases']} match cases, {dataset['rankings']} ranking pairs |",
        f"| Run started | {run['started_at']} |",
        f"| Git commit | `{run['git_commit']}`"
        + (" (uncommitted changes present)" if run.get("git_dirty") else "")
        + " |",
        f"| Live AI evaluation | {'RAN' if live['ran'] else 'NOT RUN'}"
        + (f" ({_escape(live.get('reason', ''))})" if not live["ran"] else "")
        + " |",
        "",
    ]

    if live["ran"]:
        lines += ["Live providers:", ""]
        for key, value in live.get("providers", {}).items():
            lines.append(f"- {key}: {value['provider']} / `{value['model']}`")
        lines.append("")

    lines += ["Pipeline versions:", ""]
    lines += [f"- {key}: `{value}`" for key, value in report["pipeline_versions"].items()]
    lines.append("")

    summary = report["summary"]
    lines += ["## Summary", "", "| Capability | Cases |", "|---|---|"]
    lines += [f"| {key} | {value} |" for key, value in summary["cases"].items()]
    lines += ["", "Alternative requirements (\"A or B\"):", ""]
    lines += [
        f"- {key}: {'n/a' if value is None else value}"
        for key, value in summary["alternative_requirements"].items()
    ]
    lines += ["", f"Items needing human review: {summary['human_review_items']}", ""]

    for capability in report["capabilities"]:
        lines += [
            f"## {capability['title']}",
            "",
            f"- Mode: {capability['mode']}",
            f"- Stage: {capability['stage']}",
            f"- Cases: {capability['cases_passed']}/{capability['cases_evaluated']} passed, "
            f"{capability['cases_errored']} errored (error rate "
            f"{'n/a' if capability['error_rate'] is None else capability['error_rate']})",
            "",
            "| Metric | Value |",
            "|---|---|",
        ]
        lines += [
            f"| {name} | {_format_value(metric)} |"
            for name, metric in capability["metrics"].items()
        ]
        lines.append("")

        findings = capability["findings"]
        if findings:
            for category, label in CATEGORY_LABELS.items():
                items = [item for item in findings if item["category"] == category]
                if not items:
                    continue
                lines += [f"**{label}** ({len(items)})", ""]
                lines += [f"- {item['case_id']}: {_escape(item['detail'])}" for item in items]
                lines.append("")
        else:
            lines += ["No findings.", ""]

        for note in capability["notes"]:
            lines.append(f"> {note}")
        if capability["notes"]:
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _flatten(report: dict) -> dict[str, dict]:
    return {
        f"{capability['capability']}.{name}": metric
        for capability in report["capabilities"]
        for name, metric in capability["metrics"].items()
    }


def _passed_cases(report: dict) -> dict[str, bool]:
    return {
        f"{capability['capability']}.{case['case_id']}": case["passed"]
        for capability in report["capabilities"]
        for case in capability["cases"]
    }


def compare_reports(baseline: dict, current: dict, *, tolerance: float = 0.0) -> dict:
    """Compare `current` to `baseline`.

    A metric regresses when it moves in the wrong direction by more than
    `tolerance`, or when it had a value and now has none. A case
    regresses when it passed in the baseline and fails now. Metrics or
    cases that only exist on one side are listed, never silently
    ignored.
    """
    before, after = _flatten(baseline), _flatten(current)
    regressions: list[dict] = []
    improvements: list[dict] = []

    for name in sorted(before.keys() & after.keys()):
        old, new = before[name].get("value"), after[name].get("value")
        direction = after[name].get("direction", "higher")
        entry = {"metric": name, "baseline": old, "current": new, "direction": direction}

        if old is None or new is None:
            if old is not None and new is None:
                regressions.append(entry)
            continue

        delta = new - old if direction == "higher" else old - new

        if delta < -tolerance:
            regressions.append(entry)
        elif delta > tolerance:
            improvements.append(entry)

    cases_before, cases_after = _passed_cases(baseline), _passed_cases(current)
    case_regressions = sorted(
        name
        for name in cases_before.keys() & cases_after.keys()
        if cases_before[name] and not cases_after[name]
    )
    case_fixes = sorted(
        name
        for name in cases_before.keys() & cases_after.keys()
        if not cases_before[name] and cases_after[name]
    )

    return {
        "baseline_dataset_version": baseline["dataset"]["version"],
        "current_dataset_version": current["dataset"]["version"],
        "dataset_version_changed": baseline["dataset"]["version"] != current["dataset"]["version"],
        "regressions": regressions,
        "improvements": improvements,
        "case_regressions": case_regressions,
        "case_fixes": case_fixes,
        "metrics_only_in_baseline": sorted(before.keys() - after.keys()),
        "metrics_only_in_current": sorted(after.keys() - before.keys()),
    }


def render_comparison(comparison: dict) -> str:
    lines = ["## Comparison with baseline", ""]

    if comparison["dataset_version_changed"]:
        lines += [
            f"WARNING: dataset version changed ({comparison['baseline_dataset_version']} -> "
            f"{comparison['current_dataset_version']}); metrics are not directly comparable.",
            "",
        ]

    for key, title in (
        ("regressions", "Metric regressions"),
        ("improvements", "Metric improvements"),
    ):
        lines += [f"{title}: {len(comparison[key])}", ""]
        lines += [
            f"- {item['metric']}: {item['baseline']} -> {item['current']} "
            f"({item['direction']} is better)"
            for item in comparison[key]
        ]
        lines.append("")

    for key, title in (
        ("case_regressions", "Cases that now fail"),
        ("case_fixes", "Cases that now pass"),
        ("metrics_only_in_baseline", "Metrics missing from this run"),
        ("metrics_only_in_current", "New metrics"),
    ):
        lines += [f"{title}: {len(comparison[key])}", ""]
        lines += [f"- {item}" for item in comparison[key]]
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
