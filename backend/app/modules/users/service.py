"""User profile business logic (ownership is enforced via the auth context)."""

from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.schemas import (
    PatchMeRequest,
    PatchPreferencesRequest,
    PreferencesData,
)


def get_me(db: Session, user: User) -> User:
    # Refresh from the DB so profile edits in this session are visible.
    db.refresh(user)
    return user


def patch_me(db: Session, user: User, payload: PatchMeRequest) -> User:
    profile = user.profile
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(user)
    return user


def get_preferences(db: Session, user: User) -> PreferencesData:
    db.refresh(user)
    stored = user.profile.preferences or {}
    return PreferencesData.model_validate(stored)


def patch_preferences(db: Session, user: User, payload: PatchPreferencesRequest) -> PreferencesData:
    profile = user.profile
    updates = payload.model_dump(exclude_unset=True)
    merged = {**(profile.preferences or {}), **updates}
    validated = PreferencesData.model_validate(merged)
    profile.preferences = validated.model_dump()
    db.commit()
    db.refresh(user)
    return validated
