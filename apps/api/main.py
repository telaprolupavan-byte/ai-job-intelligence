from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers.auth import router as auth_router
from apps.api.routers.dashboard import router as dashboard_router
from apps.api.routers.preferences import router as preferences_router
from apps.api.routers.profile import router as profile_router
from apps.api.routers.resumes import router as resumes_router

app = FastAPI(
    title="AI Job Intelligence API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(preferences_router)
app.include_router(resumes_router)
app.include_router(dashboard_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}