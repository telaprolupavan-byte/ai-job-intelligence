from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import Resume, ResumeVersion, User
from apps.api.schemas import (
    ResumeDetailResponse,
    ResumeResponse,
    ResumeValidationResponse,
)
from apps.api.services.resume_parser import extract_resume_text
from apps.api.services.resume_service import save_uploaded_resume
from apps.api.services.resume_validation import validate_resume_text


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