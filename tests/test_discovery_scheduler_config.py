"""Config-presence tests for the Job Discovery scheduler (AJI-017.1).

These don't run the scheduler container (this repo's test suite has no
Docker access, and PyYAML isn't a project dependency) - they verify the
checked-in configuration itself, as text: that the scheduler service is
actually wired into docker-compose.yml, that it targets the existing
(and only) discovery trigger endpoint using the existing trigger-token
mechanism, and that no secret is hardcoded into either the compose file
or the script.

The scheduler script's runtime behavior (calls the endpoint, logs the
response, tolerates failures without exiting, retries on the next
interval, skips cleanly when unconfigured) was verified directly by
running deploy/discovery-scheduler/run_scheduler.sh with `sh` against a
real running instance of this application during development - see the
AJI-017.1 report for that transcript. That can't be repeated as an
automated pytest test without a real HTTP server and an `sh` subshell
running an infinite loop, so this file focuses on what *can* be asserted
reliably and quickly: the configuration is correct and internally
consistent.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_TEXT = (REPO_ROOT / "docker-compose.yml").read_text()
SCHEDULER_DIR = REPO_ROOT / "deploy" / "discovery-scheduler"


def _service_block(service_name: str) -> str:
    """Return the raw text of one top-level service's block from
    docker-compose.yml, up to (but not including) the next top-level
    `services:`-indented key. Good enough for these presence/consistency
    checks without adding a YAML-parsing dependency to the project."""
    pattern = re.compile(
        rf"^  {re.escape(service_name)}:\n(.*?)(?=^  \S|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(COMPOSE_TEXT)
    assert match, f"service {service_name!r} not found in docker-compose.yml"
    return match.group(1)


def test_docker_compose_defines_a_discovery_scheduler_service():
    assert "discovery-scheduler:" in COMPOSE_TEXT


def test_scheduler_service_depends_on_api():
    scheduler_block = _service_block("discovery-scheduler")
    assert "- api" in scheduler_block


def test_scheduler_service_has_required_environment():
    scheduler_block = _service_block("discovery-scheduler")
    assert "DISCOVERY_API_URL" in scheduler_block
    assert "DISCOVERY_INTERVAL_SECONDS" in scheduler_block
    assert (
        "JOB_DISCOVERY_TRIGGER_TOKEN: ${JOB_DISCOVERY_TRIGGER_TOKEN:-}"
        in scheduler_block
    )


def test_api_and_scheduler_reference_the_same_trigger_token_variable():
    """Both services must source the token from the same shell/.env
    variable name - otherwise the scheduler's requests would never
    authenticate against the API it's meant to call."""
    api_block = _service_block("api")
    scheduler_block = _service_block("discovery-scheduler")

    token_line = "JOB_DISCOVERY_TRIGGER_TOKEN: ${JOB_DISCOVERY_TRIGGER_TOKEN:-}"
    assert token_line in api_block
    assert token_line in scheduler_block


def test_no_discovery_secret_is_hardcoded_in_compose():
    """Every JOB_DISCOVERY_* value in docker-compose.yml must come from a
    ${VAR} substitution, never a literal value baked into the committed
    file."""
    for line in COMPOSE_TEXT.splitlines():
        stripped = line.strip()
        if not stripped.startswith("JOB_DISCOVERY_"):
            continue
        key, _, value = stripped.partition(":")
        value = value.strip()
        assert value.startswith("${") and value.endswith("}"), (
            f"{key} must be a ${{...}} substitution in docker-compose.yml, "
            f"got literal value {value!r}"
        )


def test_scheduler_dockerfile_and_script_exist():
    assert (SCHEDULER_DIR / "Dockerfile").is_file()
    assert (SCHEDULER_DIR / "run_scheduler.sh").is_file()


def test_scheduler_dockerfile_runs_the_script_without_a_shell_command_override():
    dockerfile_text = (SCHEDULER_DIR / "Dockerfile").read_text()
    assert "run_scheduler.sh" in dockerfile_text
    assert "ENTRYPOINT" in dockerfile_text


def test_scheduler_script_targets_the_existing_discovery_trigger_endpoint():
    script_text = (SCHEDULER_DIR / "run_scheduler.sh").read_text()
    assert "/internal/job-discovery/run" in script_text
    assert "X-Discovery-Trigger-Token" in script_text
    # It must read the token from the environment, never embed one.
    assert "${JOB_DISCOVERY_TRIGGER_TOKEN" in script_text


def test_scheduler_script_never_exits_on_a_failed_call():
    """The loop body must always `return 0` from run_once, and the outer
    loop must have no break/exit condition, so a curl failure, a 502/503
    from the API, or a 409 from an overlapping run can never stop future
    scheduled attempts."""
    script_text = (SCHEDULER_DIR / "run_scheduler.sh").read_text()
    assert "while true" in script_text
    assert "return 0" in script_text

    code_lines = [
        line
        for line in script_text.splitlines()
        if not line.strip().startswith("#")
    ]
    # No bare `exit <nonzero>` anywhere that would kill the loop's
    # process from within run_once on a failed call.
    assert not any(
        re.match(r"^\s*exit\s+[1-9]", line) for line in code_lines
    )


def test_scheduler_script_does_not_hardcode_a_trigger_token():
    script_text = (SCHEDULER_DIR / "run_scheduler.sh").read_text()
    for line in script_text.splitlines():
        if "JOB_DISCOVERY_TRIGGER_TOKEN=" in line:
            # Only acceptable form: reading it from the environment via
            # ${JOB_DISCOVERY_TRIGGER_TOKEN...}, never assigning a literal.
            assert "${JOB_DISCOVERY_TRIGGER_TOKEN" in line, (
                f"suspicious literal token assignment: {line!r}"
            )
