from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status


BASE_DIR = Path(__file__).resolve().parents[3]
RESUME_UPLOAD_DIR = BASE_DIR / "uploads" / "resumes"

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def validate_resume_file(filename: str | None) -> str:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A resume filename is required.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX resumes are supported.",
        )

    return extension


async def save_uploaded_resume(
    file: UploadFile,
) -> tuple[str, Path]:
    extension = validate_resume_file(file.filename)

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Resume file must be 10 MB or smaller.",
        )

    RESUME_UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stored_filename = f"{uuid4()}{extension}"
    destination = RESUME_UPLOAD_DIR / stored_filename

    destination.write_bytes(contents)

    return stored_filename, destination