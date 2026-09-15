from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Resume, ResumeVersion, User
from schemas import ResumeDetailResponse, ResumeResponse
from services.resume_parser import extract_resume_text
from services.resume_service import save_uploaded_resume


router = APIRouter(
    prefix="/resumes",
    tags=["Resumes"],
)


@router.post(
    "/upload",
    response_model=ResumeDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stored_filename, storage_path = await save_uploaded_resume(file)

    original_text = extract_resume_text(storage_path)

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

    return ResumeDetailResponse(
        id=str(resume.id),
        filename=resume.filename,
        original_text=resume.original_text,
        created_at=resume.created_at.isoformat(),
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