from __future__ import annotations

from services.provider_scorecard.contracts import SearchScenario

# Illustrative only - NOT an approved canonical scenario set. Which search
# scenarios represent NERO's real target users (titles, locations, remote
# preferences) is a product decision, same as the "which company's board to
# ingest" call the Job Discovery config deliberately leaves unset by
# default (see services/job_discovery/README.md). A Product Owner should
# supply the real, approved scenario list to run_provider_scorecard()/
# compare_providers() - these exist so the pipeline is runnable/testable
# before that list exists, not to preempt it.
EXAMPLE_SCENARIOS: list[SearchScenario] = [
    SearchScenario(
        scenario_id="backend-remote",
        description="Backend engineer, remote, no location filter",
        keywords="backend engineer",
        location=None,
        remote_preference="remote",
    ),
    SearchScenario(
        scenario_id="frontend-nyc",
        description="Frontend engineer, New York NY, no remote filter",
        keywords="frontend engineer",
        location="New York, NY",
        remote_preference=None,
    ),
    SearchScenario(
        scenario_id="data-analyst-hybrid-sf",
        description="Data analyst, hybrid, San Francisco CA",
        keywords="data analyst",
        location="San Francisco, CA",
        remote_preference="hybrid",
    ),
]
