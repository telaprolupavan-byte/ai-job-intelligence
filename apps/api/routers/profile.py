from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Profile, User
from schemas import ProfileResponse, ProfileUpdate


router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)


def profile_to_response(profile: Profile) -> ProfileResponse:
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        full_name=profile.full_name,
        phone=profile.phone,
        location=profile.location,
        summary=profile.summary,
        years_experience=profile.years_experience,
        target_titles=profile.target_titles,
    )


@router.get(
    "/me",
    response_model=ProfileResponse | None,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(Profile)
        .filter(Profile.user_id == current_user.id)
        .first()
    )

    if profile is None:
        return None

    return profile_to_response(profile)


@router.put(
    "/me",
    response_model=ProfileResponse,
)
def update_my_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(Profile)
        .filter(Profile.user_id == current_user.id)
        .first()
    )

    if profile is None:
        profile = Profile(
            user_id=current_user.id,
        )
        db.add(profile)

    update_data = profile_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return profile_to_response(profile)