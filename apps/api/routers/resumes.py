from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import Resume, ResumeAIAnalysis, ResumeVersion, User
from apps.api.schemas import (
    ResumeDetailResponse,
    ResumeResponse,
    ResumeVersionResponse,
    ResumeValidationResponse,
)
from apps.api.services.resume_parser import extract_resume_text
from apps.api.services.resume_service import save_uploaded_resume
from apps.api.services.resume_validation import validate_resume_text
from apps.api.services.resume_ai.service import (
    ResumeAIServiceError,
    analyze_resume_version,
)


router = APIRouter(
    prefix="/resumes",
    tags=["Resumes"],
)


@router.post(
    "/upload",
    response_model=ResumeValidationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stored_filename, storage_path = await save_uploaded_resume(file)

    try:
        original_text = extract_resume_text(storage_path)
        validation = validate_resume_text(original_text)

        if not validation.valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": (
                        "The uploaded document could not be validated "
                        "as a usable resume."
                    ),
                    "warnings": validation.warnings,
                },
            )

        resume = Resume(
            user_id=current_user.id,
            filename=file.filename,
            storage_path=str(storage_path),
            original_text=original_text,
        )

        db.add(resume)
        db.flush()

        version = ResumeVersion(
            resume_id=resume.id,
            name="Original",
            content_text=original_text,
            is_master=True,
        )

        db.add(version)
        db.commit()
        db.refresh(resume)

        return ResumeValidationResponse(
            id=str(resume.id),
            filename=resume.filename,
            created_at=resume.created_at.isoformat(),
            valid=validation.valid,
            word_count=validation.word_count,
            character_count=validation.character_count,
            section_matches=validation.section_matches,
            warnings=validation.warnings,
        )

    except HTTPException:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise

    except Exception:
        db.rollback()
        storage_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process the uploaded resume.",
        )


@router.get(
    "",
    response_model=list[ResumeResponse],
)
def list_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .all()
    )

    return [
        ResumeResponse(
            id=str(resume.id),
            filename=resume.filename,
            created_at=resume.created_at.isoformat(),
            has_text=bool(resume.original_text),
        )
        for resume in resumes
    ]


@router.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
)
def get_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        resume_uuid = UUID(resume_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_uuid,
            Resume.user_id == current_user.id,
        )
        .first()
    )

    if resume is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )

    return ResumeDetailResponse(
        id=str(resume.id),
        filename=resume.filename,
        original_text=resume.original_text,
        created_at=resume.created_at.isoformat(),
    )


@router.get(
    "/{resume_id}/versions",
    response_model=list[ResumeVersionResponse],
)
def list_resume_versions(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        resume_uuid = UUID(resume_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_uuid,
            Resume.user_id == current_user.id,
        )
        .first()
    )

    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    return [
        ResumeVersionResponse(
            id=str(version.id),
            resume_id=str(version.resume_id),
            name=version.name,
            is_master=version.is_master,
            created_at=version.created_at.isoformat(),
        )
        for version in sorted(
            resume.versions,
            key=lambda version: version.created_at,
            reverse=True,
        )
    ]


@router.post(
    "/versions/{resume_version_id}/ai-analysis",
)
def create_resume_ai_analysis(
    resume_version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return analyze_resume_version(
            db=db,
            user_id=current_user.id,
            resume_version_id=resume_version_id,
        )
    except ResumeAIServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc


@router.get(
    "/versions/{resume_version_id}/ai-analysis",
)
def get_resume_ai_analysis(
    resume_version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = (
        db.query(ResumeAIAnalysis)
        .filter(
            ResumeAIAnalysis.resume_version_id == resume_version_id,
            ResumeAIAnalysis.user_id == current_user.id,
        )
        .order_by(ResumeAIAnalysis.created_at.desc())
        .first()
    )

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume AI analysis not found.",
        )

    return {
        "id": str(analysis.id),
        "resume_version_id": str(analysis.resume_version_id),
        "analysis_version": analysis.analysis_version,
        "analyzer_version": analysis.analyzer_version,
        "model_provider": analysis.model_provider,
        "model_name": analysis.model_name,
        "prompt_version": analysis.prompt_version,
        "analysis_result": analysis.analysis_result,
        "created_at": analysis.created_at,
    }