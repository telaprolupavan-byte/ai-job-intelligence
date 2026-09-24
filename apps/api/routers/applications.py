from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import SavedJob, User
from apps.api.schemas import (
    ApplicationDetailResponse,
    ApplicationJobSummary,
    ApplicationResponse,
    ApplicationStatusEventResponse,
    CreateApplicationRequest,
    UpdateApplicationStatusRequest,
)
from apps.api.services.application_service import (
    ApplicationServiceError,
    create_application,
    get_application,
    list_applications,
    remove_saved_job,
    update_application_status,
)
from services.job_discovery.sources.non_production import (
    is_non_production_source,
)


router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)


def _job_summary(saved_job: SavedJob) -> ApplicationJobSummary:
    job = saved_job.job

    return ApplicationJobSummary(
        id=str(job.id),
        title=job.title,
        company=job.company.name if job.company else None,
        location=job.location,
        employment_type=job.employment_type,
        remote_type=job.remote_type,
        application_url=job.application_url,
        is_test_data=is_non_production_source(job.source),
    )


def _to_response(saved_job: SavedJob) -> ApplicationResponse:
    return ApplicationResponse(
        id=str(saved_job.id),
        job=_job_summary(saved_job),
        status=saved_job.status,
        applied_at=(
            saved_job.applied_at.isoformat() if saved_job.applied_at else None
        ),
        created_at=saved_job.created_at.isoformat(),
        updated_at=saved_job.updated_at.isoformat(),
    )


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_job(
    request_data: CreateApplicationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        saved_job = create_application(
            db, current_user=current_user, job_id=request_data.job_id
        )
    except ApplicationServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=str(exc)
        ) from exc

    return _to_response(saved_job)


@router.get(
    "",
    response_model=list[ApplicationResponse],
)
def get_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    applications = list_applications(db, current_user=current_user)
    return [_to_response(application) for application in applications]


@router.get(
    "/{application_id}",
    response_model=ApplicationDetailResponse,
)
def get_application_detail(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        application = get_application(
            db, current_user=current_user, application_id=application_id
        )
    except ApplicationServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=str(exc)
        ) from exc

    base = _to_response(application)

    return ApplicationDetailResponse(
        **base.model_dump(),
        status_history=[
            ApplicationStatusEventResponse(
                status=event.status,
                created_at=event.created_at.isoformat(),
            )
            for event in application.status_events
        ],
    )


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_saved_job_endpoint(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        remove_saved_job(
            db, current_user=current_user, application_id=application_id
        )
    except ApplicationServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=str(exc)
        ) from exc


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
)
def update_status(
    application_id: str,
    request_data: UpdateApplicationStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        application = update_application_status(
            db,
            current_user=current_user,
            application_id=application_id,
            status=request_data.status,
        )
    except ApplicationServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=str(exc)
        ) from exc

    return _to_response(application)
