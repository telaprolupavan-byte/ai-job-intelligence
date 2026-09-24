"""AJI-031 evaluation command.

    python -m services.ai_evaluation.run_eval                  # deterministic
    python -m services.ai_evaluation.run_eval --live           # + live LLM stages
    python -m services.ai_evaluation.run_eval \\
        --compare services/ai_evaluation/baselines/v1-deterministic.json

Writes `report.json` and `report.md` to `--output-dir` (default:
`ai-evaluation-output/`, git-ignored). Exit codes: 0 success, 1
regressions found with `--fail-on-regression`, 2 `--live` requested but
the live stage could not run, 3 invalid dataset.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the NERO AI evaluation (AJI-031).")
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also call the real AI providers (needs OPENAI_API_KEY; costs money).",
    )
    parser.add_argument("--output-dir", default="ai-evaluation-output")
    parser.add_argument("--compare", help="Baseline report.json to compare against.")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--fail-on-regression", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Importing the API package loads its settings, which require a JWT
    # secret. The evaluation never authenticates anyone, so a placeholder
    # is supplied only when none is configured.
    os.environ.setdefault("JWT_SECRET_KEY", "ai-evaluation-unused")

    from services.ai_evaluation.dataset import DatasetError, load_dataset
    from services.ai_evaluation.report import (
        compare_reports,
        render_comparison,
        render_markdown,
    )
    from services.ai_evaluation.runner import run_evaluation

    try:
        dataset = load_dataset(args.dataset_version)
    except DatasetError as exc:
        print(f"Invalid evaluation dataset: {exc}", file=sys.stderr)
        return 3

    report = run_evaluation(dataset, live=args.live)
    markdown = render_markdown(report)
    exit_code = 0

    if args.compare:
        baseline = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        comparison = compare_reports(baseline, report, tolerance=args.tolerance)
        report["comparison"] = comparison
        markdown += "\n" + render_comparison(comparison)

        if args.fail_on_regression and (
            comparison["regressions"] or comparison["case_regressions"]
        ):
            exit_code = 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(markdown, encoding="utf-8")

    for line in report["summary"]["cases"].items():
        print(f"{line[0]}: {line[1]}")
    print(f"Report written to {output_dir / 'report.md'}")

    live = report["run"]["live_ai"]
    if args.live and not live["ran"]:
        print(f"Live AI evaluation NOT RUN: {live.get('reason')}", file=sys.stderr)
        return 2

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
