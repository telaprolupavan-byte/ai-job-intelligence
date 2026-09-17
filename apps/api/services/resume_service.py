from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status


BASE_DIR = Path(__file__).resolve().parents[3]
RESUME_UPLOAD_DIR = (BASE_DIR / "uploads" / "resumes").resolve()

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


async def read_uploaded_resume(
    file: UploadFile,
) -> tuple[str, bytes]:
    """Validate and read an uploaded resume file into memory.

    Reading (rather than writing to disk immediately) lets the caller
    determine whether this content is an exact duplicate of an existing
    resume version *before* any physical file is created.
    """
    extension = validate_resume_file(file.filename)

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Resume file must be 10 MB or smaller.",
        )

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded resume file is empty.",
        )

    return extension, contents


def store_resume_file(
    *,
    user_id: UUID,
    resume_id: UUID,
    version_id: UUID,
    extension: str,
    contents: bytes,
) -> Path:
    """Persist resume bytes at a collision-safe, non-guessable path.

    The path is derived entirely from server-generated identifiers
    (never from the client-supplied filename), so two uploads can never
    collide and a client can never influence where a file is written.
    """
    version_dir = RESUME_UPLOAD_DIR / str(user_id) / str(resume_id)
    version_dir.mkdir(parents=True, exist_ok=True)

    destination = version_dir / f"{version_id}{extension}"
    destination.write_bytes(contents)

    return destination


def resolve_stored_file(storage_path: str) -> Path:
    """Resolve a DB-stored path to a real file, rejecting anything that
    would escape the resume uploads directory (defense in depth against
    path traversal, even though storage_path is always server-generated
    and never derived from client input)."""
    resolved = Path(storage_path).resolve()

    if not resolved.is_relative_to(RESUME_UPLOAD_DIR):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume file not found.",
        )

    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume file not found.",
        )

    return resolved
