"""User profile business logic (ownership is enforced via the auth context)."""

from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.schemas import PatchMeRequest


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
