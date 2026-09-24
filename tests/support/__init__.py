"""Shared backend test infrastructure (AJI-032B).

Modules here hold test doubles and fixture builders reused by more than
one test module, so tests import shared helpers from `tests.support`
instead of from each other. Keep them lightweight: they may import
application models, contracts and services, but never routers or the
FastAPI app.

- `general_resume`: AJI-027 resume texts, provider double, user/version builders
- `job_discovery`: AJI-028 synthetic paged provider (never registered)
- `job_intelligence`: persisted `JobIntelligence` rows and legacy items
- `requirement_intelligence`: persisted `RequirementIntelligence` rows and items
"""
