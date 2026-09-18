"""
Evaluation-only provider adapters for the Provider Scorecard Workflow.

These are NOT production `services.job_discovery.sources.JobSourceAdapter`
implementations, and this package is not wired into Job Discovery, the
API, or the database anywhere. Each adapter here exists solely to feed
`services.provider_scorecard.pipeline.run_provider_scorecard`/
`compare_providers` so a candidate provider's raw data quality can be
measured before anyone decides whether it is worth building a real
adapter for (see docs/ARCHITECTURE.md, "Provider Scorecard Workflow").

Every adapter reads its own credentials from environment variables via a
`from_env()` classmethod that returns `None` when unconfigured (mirroring
`apps/api/services/job_discovery_service.py::build_configured_source`'s
"never run with an implicit/guessed source" convention) rather than
raising or fabricating a result - `services/provider_scorecard/run_eval.py`
skips whatever isn't configured instead of failing the whole comparison.

Field mappings below are based on each provider's published public API
documentation, not a live response verified from this repository (the
sandboxed environment these adapters were authored in has no outbound
network access to any of these hosts - see run_eval.py's module
docstring). Treat the first real run's raw output as the actual
verification step, and expect to adjust field names if a provider's API
has since changed.
"""
