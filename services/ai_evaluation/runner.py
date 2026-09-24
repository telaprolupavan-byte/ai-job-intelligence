"""Runs every AJI-031 evaluator and assembles one report.

Two clearly separated modes:

- Deterministic (always runs, no credentials, no network): every
  production pipeline whose output does not depend on an LLM.
- Live (`live=True`): additionally calls the real AI providers through
  the existing provider factories for the three LLM stages (Resume
  Intelligence, and the Job/Requirement Intelligence semantic stage). If
  the providers cannot be created (for example no OPENAI_API_KEY), the
  live section is recorded as NOT RUN with the reason. It is never
  replaced by mocked output.
"""

from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from services.ai_evaluation import pipelines
from services.ai_evaluation.dataset import EvaluationDataset
from services.ai_evaluation.evaluators.general_resume import (
    evaluate_general_resume_score,
)
from services.ai_evaluation.evaluators.job import (
    evaluate_ai_semantics_live,
    evaluate_job_intelligence,
)
from services.ai_evaluation.evaluators.matching import (
    evaluate_gap_analysis,
    evaluate_job_match,
)
from services.ai_evaluation.evaluators.requirement import (
    evaluate_requirement_intelligence,
)
from services.ai_evaluation.evaluators.resume import (
    evaluate_resume_deterministic,
    evaluate_resume_live,
)
from services.ai_evaluation.results import CapabilityResult


REPORT_SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return None


def pipeline_versions() -> dict[str, str]:
    from apps.api.services.general_resume.scoring import SCORING_VERSION
    from apps.api.services.job_intelligence.interpreter import (
        PROMPT_VERSION as JOB_PROMPT_VERSION,
    )
    from apps.api.services.job_intelligence.service import (
        ANALYZER_VERSION as JOB_ANALYZER_VERSION,
    )
    from apps.api.services.requirement_intelligence.interpreter import (
        PROMPT_VERSION as REQUIREMENT_PROMPT_VERSION,
    )
    from apps.api.services.requirement_intelligence.service import (
        ANALYZER_VERSION as REQUIREMENT_ANALYZER_VERSION,
    )
    from apps.api.services.resume_ai.interpreter import (
        PROMPT_VERSION as RESUME_PROMPT_VERSION,
    )
    from apps.api.services.resume_ai.service import (
        ANALYZER_VERSION as RESUME_ANALYZER_VERSION,
    )
    from services.ats_alignment.engine import ENGINE_VERSION as ATS_ENGINE_VERSION
    from services.job_matching.scorer import ENGINE_VERSION as MATCH_ENGINE_VERSION

    return {
        "resume_analyzer": RESUME_ANALYZER_VERSION,
        "resume_prompt": RESUME_PROMPT_VERSION,
        "job_intelligence_analyzer": JOB_ANALYZER_VERSION,
        "job_intelligence_prompt": JOB_PROMPT_VERSION,
        "requirement_intelligence_analyzer": REQUIREMENT_ANALYZER_VERSION,
        "requirement_intelligence_prompt": REQUIREMENT_PROMPT_VERSION,
        "job_match_engine": MATCH_ENGINE_VERSION,
        "ats_alignment_engine": ATS_ENGINE_VERSION,
        "general_resume_scoring": SCORING_VERSION,
    }


def run_deterministic(dataset: EvaluationDataset) -> list[CapabilityResult]:
    return [
        evaluate_resume_deterministic(dataset),
        evaluate_job_intelligence(dataset),
        evaluate_requirement_intelligence(dataset),
        evaluate_job_match(dataset),
        evaluate_gap_analysis(dataset),
        evaluate_general_resume_score(dataset),
    ]


def create_live_providers() -> dict:
    """Create the three production providers. Raises when they cannot be
    created (e.g. no API key), which the caller records as NOT RUN."""
    from apps.api.services.job_intelligence.providers import (
        create_job_intelligence_provider,
    )
    from apps.api.services.requirement_intelligence.providers import (
        create_requirement_intelligence_provider,
    )
    from apps.api.services.resume_ai.providers import create_resume_ai_provider

    return {
        "resume": create_resume_ai_provider(),
        "job": create_job_intelligence_provider(),
        "requirement": create_requirement_intelligence_provider(),
    }


def run_live(dataset: EvaluationDataset, providers: dict) -> list[CapabilityResult]:
    return [
        evaluate_resume_live(
            dataset,
            lambda resume: pipelines.live_resume_intelligence(resume, providers["resume"]),
        ),
        evaluate_ai_semantics_live(
            dataset,
            lambda job: pipelines.live_job_intelligence(job, providers["job"]),
            capability="job_intelligence_live",
            title="Job Intelligence: AI semantic stage (live)",
            stage="job_intelligence provider + interpreter + validator",
            raw_text=pipelines.job_raw_text,
            baseline=pipelines.run_job_intelligence,
        ),
        evaluate_ai_semantics_live(
            dataset,
            lambda job: pipelines.live_requirement_intelligence(job, providers["requirement"]),
            capability="requirement_intelligence_live",
            title="Requirement Intelligence: AI semantic stage (live)",
            stage="requirement_intelligence provider + interpreter + validator",
            raw_text=lambda job: pipelines.requirement_raw_text(
                pipelines.raw_requirement_source(job)
            ),
            baseline=pipelines.run_requirement_intelligence,
        ),
    ]


def _summary(capabilities: list[dict]) -> dict:
    by_name = {item["capability"]: item for item in capabilities}

    def metric(capability: str, name: str):
        return by_name.get(capability, {}).get("metrics", {}).get(name, {}).get("value")

    injection_findings = [
        {"capability": item["capability"], **finding}
        for item in capabilities
        for finding in item["findings"]
        if finding["category"] == "prompt_injection"
    ]

    return {
        "cases": {
            item["capability"]: f"{item['cases_passed']}/{item['cases_evaluated']} passed"
            for item in capabilities
        },
        "alternative_requirements": {
            "requirement_intelligence_or_group_recall": metric(
                "requirement_intelligence", "or_group_recall"
            ),
            "job_match_or_group_correctness": metric(
                "job_match", "alternative_or_group_correctness"
            ),
            "gap_analysis_or_group_correctness": metric(
                "gap_analysis", "alternative_or_group_correctness"
            ),
        },
        "prompt_injection_findings": injection_findings,
        "human_review_items": sum(
            item["finding_counts"].get("human_review", 0) for item in capabilities
        ),
    }


def run_evaluation(
    dataset: EvaluationDataset,
    *,
    live: bool = False,
    providers: dict | None = None,
) -> dict:
    started = datetime.now(timezone.utc)
    results = run_deterministic(dataset)

    live_status: dict = {"requested": live, "ran": False}

    if live:
        try:
            providers = providers or create_live_providers()
        except Exception as exc:
            live_status["reason"] = f"{type(exc).__name__}: {exc}"
        else:
            results.extend(run_live(dataset, providers))
            live_status.update(
                ran=True,
                providers={
                    key: {
                        "provider": getattr(value, "provider_name", None),
                        "model": getattr(value, "model_name", None),
                    }
                    for key, value in providers.items()
                },
            )
    else:
        live_status["reason"] = "Not requested (run with --live)."

    capabilities = [item.to_dict() for item in results]

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "ticket": "AJI-031",
        "run": {
            "started_at": started.isoformat(timespec="seconds"),
            "git_commit": _git("rev-parse", "HEAD"),
            # True when the working tree had uncommitted changes, i.e. the
            # results may not correspond exactly to `git_commit`.
            "git_dirty": bool(_git("status", "--porcelain")),
            "python": platform.python_version(),
            "live_ai": live_status,
        },
        "dataset": {
            "name": dataset.manifest.dataset,
            "version": dataset.manifest.version,
            "synthetic": dataset.manifest.synthetic,
            "resumes": len(dataset.resumes),
            "jobs": len(dataset.jobs),
            "match_cases": len(dataset.match_cases),
            "rankings": len(dataset.manifest.rankings),
        },
        "pipeline_versions": pipeline_versions(),
        "capabilities": capabilities,
        "summary": _summary(capabilities),
    }
