from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.models import User
from apps.api.security import decode_access_token


bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        user_id = decode_access_token(token)
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_uuid).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

optional_bearer_scheme = HTTPBearer(auto_error=False)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        optional_bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User | None:
    """The authenticated user on a public endpoint, or None.

    A missing, invalid, or expired token means "anonymous" rather than a
    401: the endpoint is public, so a stale token in the browser must not
    break it - it just gets the anonymous view.
    """
    if credentials is None:
        return None

    try:
        user_uuid = UUID(decode_access_token(credentials.credentials))
    except (ValueError, TypeError):
        return None

    return db.query(User).filter(User.id == user_uuid).first()
