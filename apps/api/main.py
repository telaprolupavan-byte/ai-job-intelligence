from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import settings
from apps.api.routers.auth import router as auth_router
from apps.api.routers.dashboard import router as dashboard_router
from apps.api.routers.preferences import router as preferences_router
from apps.api.routers.profile import router as profile_router
from apps.api.routers.resumes import router as resumes_router
from apps.api.routers.jobs import router as jobs_router
from apps.api.routers.job_discovery import router as job_discovery_router
from apps.api.routers.job_discovery import (
    status_router as job_discovery_status_router,
)
from apps.api.routers.applications import router as applications_router

app = FastAPI(
    title="AI Job Intelligence API",
    version="0.1.0",
)

# Local dev origins are always allowed; the configured frontend_url (e.g.
# a production domain) is added on top so deploying doesn't silently break
# CORS until someone remembers to edit this list by hand.
_cors_allowed_origins = {
    "http://localhost:3000",
    "http://localhost:3001",
    settings.frontend_url,
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(preferences_router)
app.include_router(resumes_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(job_discovery_router)
app.include_router(job_discovery_status_router)
app.include_router(applications_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}