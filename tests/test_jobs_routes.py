"""AJI-034 - the /jobs route table, now split across apps/api/routers/jobs/.

Pins what the split must never change: every /jobs route, the order they
are registered in, and the endpoint each request resolves to - above all
that GET /jobs/priority is never read as GET /jobs/{job_id}.

No database: the auth dependencies are overridden to report which
endpoint the request was routed to, so no handler body ever runs.
"""

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from apps.api.dependencies import (
    get_current_user,
    get_db,
    get_optional_current_user,
)
from apps.api.main import app


JOB_ID = "3f1c2a8e-0000-4000-8000-000000000001"
IMPROVEMENT_ID = "3f1c2a8e-0000-4000-8000-000000000002"

# (method, path, module in apps.api.routers.jobs, endpoint), in
# registration order. Changing this table changes the public API.
JOB_ROUTES = [
    ("GET", "/jobs", "search", "list_jobs"),
    ("POST", "/jobs/submissions", "submissions", "create_job_submission"),
    ("GET", "/jobs/priority", "priority", "get_job_priority"),
    ("GET", "/jobs/{job_id}", "details", "get_job"),
    ("GET", "/jobs/{job_id}/match", "match", "get_job_match"),
    ("POST", "/jobs/{job_id}/match", "match", "calculate_job_match"),
    ("GET", "/jobs/{job_id}/eligibility", "eligibility", "get_job_eligibility"),
    ("GET", "/jobs/{job_id}/intelligence", "intelligence", "get_job_intelligence"),
    ("POST", "/jobs/{job_id}/intelligence", "intelligence", "create_job_intelligence"),
    (
        "GET",
        "/jobs/{job_id}/requirement-intelligence",
        "intelligence",
        "get_requirement_intelligence",
    ),
    (
        "POST",
        "/jobs/{job_id}/requirement-intelligence",
        "intelligence",
        "create_requirement_intelligence",
    ),
    ("GET", "/jobs/{job_id}/ats", "alignment", "get_ats_alignment"),
    ("POST", "/jobs/{job_id}/ats", "alignment", "create_ats_alignment"),
    ("GET", "/jobs/{job_id}/gap-analysis", "alignment", "get_gap_analysis"),
    ("POST", "/jobs/{job_id}/gap-analysis", "alignment", "create_gap_analysis"),
    (
        "GET",
        "/jobs/{job_id}/resume-improvement",
        "resume_improvement",
        "get_resume_improvement",
    ),
    (
        "POST",
        "/jobs/{job_id}/resume-improvement",
        "resume_improvement",
        "create_job_resume_improvement",
    ),
    (
        "POST",
        "/jobs/{job_id}/resume-improvement/{improvement_id}/recheck",
        "resume_improvement",
        "retry_resume_improvement_recheck",
    ),
]


def _report_resolved_route(request: Request):
    route = request.scope["route"]
    raise HTTPException(
        status_code=418,
        detail={
            "module": route.endpoint.__module__,
            "endpoint": route.endpoint.__name__,
            "path": route.path,
        },
    )


def _no_db():
    yield None


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[get_current_user] = _report_resolved_route
    app.dependency_overrides[get_optional_current_user] = (
        _report_resolved_route
    )

    yield TestClient(app)

    app.dependency_overrides.clear()


def _resolve(client, method, path):
    response = client.request(method, path)

    assert response.status_code == 418, (method, path, response.text)

    return response.json()["detail"]


def test_jobs_routes_are_registered_in_order():
    registered = [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path == "/jobs" or path.startswith("/jobs/")
        for method in operations
    ]

    assert registered == [
        (method, path) for method, path, _, _ in JOB_ROUTES
    ]


@pytest.mark.parametrize(
    "method, path, module, endpoint",
    JOB_ROUTES,
    ids=[f"{method} {path}" for method, path, _, _ in JOB_ROUTES],
)
def test_each_jobs_route_resolves_to_its_endpoint(
    client, method, path, module, endpoint
):
    url = path.format(job_id=JOB_ID, improvement_id=IMPROVEMENT_ID)

    assert _resolve(client, method, url) == {
        "module": f"apps.api.routers.jobs.{module}",
        "endpoint": endpoint,
        "path": path,
    }


def test_priority_is_never_read_as_a_job_id(client):
    assert _resolve(client, "GET", "/jobs/priority")["endpoint"] == (
        "get_job_priority"
    )

    for job_id in (JOB_ID, "prioritized", "not-a-uuid"):
        assert _resolve(client, "GET", f"/jobs/{job_id}")["endpoint"] == (
            "get_job"
        )


def test_priority_has_no_other_methods(client):
    for method in ("POST", "PUT", "DELETE"):
        response = client.request(method, "/jobs/priority")

        assert response.status_code == 405
        assert response.headers["allow"] == "GET"
