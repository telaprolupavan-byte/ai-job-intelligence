from fastapi import FastAPI

from routers.auth import router as auth_router
from routers.profile import router as profile_router
from routers.preferences import router as preferences_router
from routers.resumes import router as resumes_router


app = FastAPI(
    title="AI Job Intelligence API",
    version="0.1.0",
)


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(preferences_router)
app.include_router(resumes_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ai-job-intelligence-api",
    }