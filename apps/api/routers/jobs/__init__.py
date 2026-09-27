"""The /jobs API, split by capability (AJI-034).

Each module serves one capability's endpoints and builds its responses;
`common.py` holds what several of them share. Only `router` is public:
it is what apps/api/main.py registers.

Registration order is behavior. A request is served by the first route
whose path matches, so GET /jobs/priority must be included before
GET /jobs/{job_id}, or "priority" would be read as a job id and 404. The
order below is exactly the order the routes had in the former single
`routers/jobs.py`, which also keeps the OpenAPI document unchanged.
tests/test_jobs_routes.py pins it.
"""

from fastapi import APIRouter

from apps.api.routers.jobs import (
    alignment,
    details,
    eligibility,
    intelligence,
    match,
    priority,
    resume_improvement,
    search,
    submissions,
)

router = APIRouter()

router.include_router(search.router)
router.include_router(submissions.router)
# Before details: see the module docstring.
router.include_router(priority.router)
router.include_router(details.router)
router.include_router(match.router)
router.include_router(eligibility.router)
router.include_router(intelligence.router)
router.include_router(alignment.router)
router.include_router(resume_improvement.router)
