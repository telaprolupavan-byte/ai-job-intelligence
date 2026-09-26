"""Shared backend test infrastructure (AJI-032B).

Helpers here are used by more than one test module. A helper used by a
single test module stays in that module. Nothing in this package imports
`apps.api.main` or a router, and no module here is named `test_*`, so
pytest never collects it as tests.

- `general_resume`: AJI-027 resume texts, a fake explanation provider,
  and user/version builders.
- `job_discovery`: the AJI-028 synthetic paged source (test double).
- `requirement_intelligence`: `RequirementIntelligence` row and item
  builders used by the ATS Alignment, Gap Analysis and Resume
  Improvement tests.
"""
