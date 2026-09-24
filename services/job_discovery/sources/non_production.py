"""The `source` values that are never production data (AJI-030).

Every synthetic provider's source is listed here, and this set - not any
one provider's constant - is what keeps synthetic jobs out of production
views: `job_access.visible_jobs_filter()` hides these rows while test mode
is off, the Jobs API flags them `is_test_data`, and the discovery status
ignores their runs. A new synthetic source must be added here; a real,
approved provider must never be.
"""

from __future__ import annotations

from services.job_discovery.sources.development_dataset import (
    DEVELOPMENT_DATASET_SOURCE,
)
from services.job_discovery.sources.test_fixture import TEST_FIXTURE_SOURCE


NON_PRODUCTION_SOURCES: frozenset[str] = frozenset(
    {TEST_FIXTURE_SOURCE, DEVELOPMENT_DATASET_SOURCE}
)


def is_non_production_source(source: str | None) -> bool:
    return source in NON_PRODUCTION_SOURCES
