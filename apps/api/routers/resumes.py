from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import Resume, ResumeAIAnalysis, ResumeVersion, User
from apps.api.schemas import (
    ResumeDetailResponse,
    ResumeResponse,
    ResumeUploadResponse,
    ResumeVersionResponse,
)
from apps.api.services.resume_parser import extract_resume_text
from apps.api.services.resume_service import (
    read_uploaded_resume,
    resolve_stored_file,
    store_resume_file,
)
from apps.api.services.resume_fingerprint import compute_content_fingerprint
from apps.api.services.resume_validation import validate_resume_text
from apps.api.services.resume_ai.service import (
    ResumeAIServiceError,
    analyze_resume_version,
)


router = APIRouter(
    prefix="/resumes",
    tags=["Resumes"],
)


MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ),
}


def _find_duplicate_version(
    db: Session,
    *,
    user_id: UUID,
    fingerprint: str,
) -> ResumeVersion | None:
    """Find an existing version with identical normalized content,
    anywhere in this user's resumes. Content identity is never based on
    filename."""
    return (
        db.query(ResumeVersion)
        .join(ResumeVersion.resume)
        .filter(
            Resume.user_id == user_id,
            ResumeVersion.content_fingerprint == fingerprint,
        )
        .order_by(ResumeVersion.created_at.desc())
        .first()
    )


def _next_version_name(db: Session, resume_id: UUID) -> str:
    existing_count = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.resume_id == resume_id)
        .count()
    )
    return f"Version {existing_count + 1}"


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
)
async def upload_resume(
    response: Response,
    file: UploadFile,
    resume_id: str | None = Form(default=None),
    version_name: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    extension, contents = await read_uploaded_resume(file)

    target_resume: Resume | None = None

    if resume_id:
        try:
            resume_uuid = UUID(resume_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found",
            )

        target_resume = (
            db.query(Resume)
            .filter(
                Resume.id == resume_uuid,
                Resume.user_id == current_user.id,
            )
            .first()
        )

        if target_resume is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found",
            )

    original_text = extract_resume_text(file.filename, contents)
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

    fingerprint = compute_content_fingerprint(original_text)

    # Exact duplicate content (regardless of filename) is never stored
    # again: reuse the existing resume/version instead of creating a
    # duplicate ResumeVersion, physical file, or AI analysis.
    duplicate = _find_duplicate_version(
        db,
        user_id=current_user.id,
        fingerprint=fingerprint,
    )

    if duplicate is not None:
        response.status_code = status.HTTP_200_OK

        return ResumeUploadResponse(
            id=str(duplicate.resume_id),
            version_id=str(duplicate.id),
            filename=duplicate.original_filename,
            version_name=duplicate.name,
            created_at=duplicate.created_at.isoformat(),
            valid=validation.valid,
            word_count=validation.word_count,
            character_count=validation.character_count,
            section_matches=validation.section_matches,
            warnings=validation.warnings,
            is_new_resume=False,
            duplicate=True,
        )

    is_new_resume = target_resume is None

    try:
        if target_resume is not None:
            resume = target_resume
            is_master = False
            name = version_name.strip() if version_name else _next_version_name(
                db, resume.id
            )
        else:
            resume = Resume(
                id=uuid4(),
                user_id=current_user.id,
                filename=file.filename,
                original_text=original_text,
            )
            db.add(resume)
            db.flush()
            is_master = True
            name = version_name.strip() if version_name else "Original"

        version_id = uuid4()

        destination = store_resume_file(
            user_id=current_user.id,
            resume_id=resume.id,
            version_id=version_id,
            extension=extension,
            contents=contents,
        )

        version = ResumeVersion(
            id=version_id,
            resume_id=resume.id,
            name=name,
            content_text=original_text,
            content_fingerprint=fingerprint,
            original_filename=file.filename,
            storage_path=str(destination),
            is_master=is_master,
        )

        db.add(version)
        db.commit()
        db.refresh(version)

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process the uploaded resume.",
        )

    response.status_code = status.HTTP_201_CREATED

    return ResumeUploadResponse(
        id=str(resume.id),
        version_id=str(version.id),
        filename=version.original_filename,
        version_name=version.name,
        created_at=version.created_at.isoformat(),
        valid=validation.valid,
        word_count=validation.word_count,
        character_count=validation.character_count,
        section_matches=validation.section_matches,
        warnings=validation.warnings,
        is_new_resume=is_new_resume,
        duplicate=False,
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

    results = []

    for resume in resumes:
        versions = resume.versions
        master = next(
            (version for version in versions if version.is_master),
            None,
        ) or (
            max(versions, key=lambda version: version.created_at)
            if versions
            else None
        )

        results.append(
            ResumeResponse(
                id=str(resume.id),
                filename=resume.filename,
                created_at=resume.created_at.isoformat(),
                has_text=bool(resume.original_text),
                version_count=len(versions),
                master_version_id=str(master.id) if master else None,
                master_version_name=master.name if master else None,
                master_version_created_at=(
                    master.created_at.isoformat() if master else None
                ),
            )
        )

    return results


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

    version_ids = [version.id for version in resume.versions]

    analyzed_version_ids = {
        row[0]
        for row in db.query(ResumeAIAnalysis.resume_version_id)
        .filter(ResumeAIAnalysis.resume_version_id.in_(version_ids))
        .distinct()
        .all()
    }

    return [
        ResumeVersionResponse(
            id=str(version.id),
            resume_id=str(version.resume_id),
            name=version.name,
            original_filename=version.original_filename,
            content_text=version.content_text,
            is_master=version.is_master,
            has_analysis=version.id in analyzed_version_ids,
            created_at=version.created_at.isoformat(),
        )
        for version in sorted(
            resume.versions,
            key=lambda version: version.created_at,
            reverse=True,
        )
    ]


@router.get(
    "/versions/{resume_version_id}/file",
)
def get_resume_version_file(
    resume_version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = (
        db.query(ResumeVersion)
        .join(ResumeVersion.resume)
        .filter(
            ResumeVersion.id == resume_version_id,
            Resume.user_id == current_user.id,
        )
        .first()
    )

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume version not found.",
        )

    file_path = resolve_stored_file(version.storage_path)
    extension = file_path.suffix.lower()

    return FileResponse(
        path=file_path,
        media_type=MEDIA_TYPES.get(extension, "application/octet-stream"),
        filename=version.original_filename,
    )


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
