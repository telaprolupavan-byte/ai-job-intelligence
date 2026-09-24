"""AJI-027 architecture guard: General Resume Intelligence stays
job-independent and separate from the job-specific pipeline."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "apps" / "api" / "services" / "general_resume"
ROUTER = Path(__file__).resolve().parents[1] / "apps" / "api" / "routers" / "general_resume.py"

FORBIDDEN_MODULE_PARTS = (
    "ats_alignment",
    "job_matching",
    "job_match_service",
    "requirement_intelligence",
    "gap_analysis",
    "job_intelligence",
    "priority_ranking",
    "eligibility",
    "routers.dashboard",
    "routers.jobs",
)


def _sources():
    return sorted(PACKAGE.rglob("*.py")) + [ROUTER]


def _imports(path):
    tree = ast.parse(path.read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_no_job_specific_imports():
    for path in _sources():
        for module in _imports(path):
            for part in FORBIDDEN_MODULE_PARTS:
                assert part not in module, f"{path.name} imports {module}"


def test_no_job_models_or_dashboard_threshold_referenced():
    for path in _sources():
        source = path.read_text()

        for name in (
            "ATS_PASS_THRESHOLD",
            "AtsAlignmentResult",
            "JobMatchResult",
            "GapAnalysis",
            "RequirementIntelligence",
            "job_id",
        ):
            assert name not in source, f"{path.name} references {name}"
