from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import PasswordResetToken, User
from apps.api.rate_limit import (
    rate_limit_forgot_password,
    rate_limit_login,
    rate_limit_register,
    rate_limit_reset_password,
)
from apps.api.schemas import (
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
)
from apps.api.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from apps.api.services.email_service import send_password_reset_email


GENERIC_FORGOT_PASSWORD_MESSAGE = (
    "If that email is registered, a password reset link has been sent."
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/test")
def auth_test():
    return {
        "message": "Authentication router is working"
    }


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    request: Request,
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    rate_limit_register(request)

    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
    )


@router.post(
    "/login",
    response_model=Token,
)
def login_user(
    request: Request,
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    rate_limit_login(request, user_data.email)

    user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if user is None or user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(
        user_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        str(user.id)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
)
def forgot_password(
    request: Request,
    request_data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    rate_limit_forgot_password(request, request_data.email)

    user = (
        db.query(User)
        .filter(User.email == request_data.email)
        .first()
    )

    # Always return the same response whether or not the email is
    # registered, so this endpoint can't be used to enumerate accounts.
    if user is not None:
        raw_token, token_hash = generate_reset_token()

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.reset_token_expire_minutes),
        )

        db.add(reset_token)
        db.commit()

        reset_url = (
            f"{settings.frontend_url}/reset-password?token={raw_token}"
        )
        send_password_reset_email(user.email, reset_url)

    return MessageResponse(message=GENERIC_FORGOT_PASSWORD_MESSAGE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
)
def reset_password(
    request: Request,
    request_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    rate_limit_reset_password(request)

    token_hash = hash_reset_token(request_data.token)

    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )

    invalid_token_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset link",
    )

    if reset_token is None or reset_token.used_at is not None:
        raise invalid_token_error

    if reset_token.expires_at < datetime.now(timezone.utc):
        raise invalid_token_error

    user = (
        db.query(User)
        .filter(User.id == reset_token.user_id)
        .first()
    )

    if user is None:
        raise invalid_token_error

    user.password_hash = hash_password(request_data.new_password)
    reset_token.used_at = datetime.now(timezone.utc)

    db.commit()

    return MessageResponse(
        message="Your password has been reset. You can now sign in."
    )