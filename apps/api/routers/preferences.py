from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Preference, User
from schemas import PreferenceResponse, PreferenceUpdate


router = APIRouter(
    prefix="/preferences",
    tags=["Preferences"],
)


def preference_to_response(
    preference: Preference,
) -> PreferenceResponse:
    return PreferenceResponse(
        id=str(preference.id),
        user_id=str(preference.user_id),
        employment_types=preference.employment_types,
        locations=preference.locations,
        remote_preference=preference.remote_preference,
        target_titles=preference.target_titles,
    )


@router.get(
    "/me",
    response_model=PreferenceResponse | None,
)
def get_my_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preference = (
        db.query(Preference)
        .filter(Preference.user_id == current_user.id)
        .first()
    )

    if preference is None:
        return None

    return preference_to_response(preference)


@router.put(
    "/me",
    response_model=PreferenceResponse,
)
def update_my_preferences(
    preference_data: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preference = (
        db.query(Preference)
        .filter(Preference.user_id == current_user.id)
        .first()
    )

    if preference is None:
        preference = Preference(
            user_id=current_user.id,
        )
        db.add(preference)

    update_data = preference_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(preference, field, value)

    db.commit()
    db.refresh(preference)

    return preference_to_response(preference)