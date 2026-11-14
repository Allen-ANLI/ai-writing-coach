"""Data access for users/profiles. No business rules here."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User, UserProfile


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def create_with_profile(
    db: Session, *, email: str, password_hash: str, display_name: str | None
) -> User:
    user = User(email=email, password_hash=password_hash, status="active")
    user.profile = UserProfile(display_name=display_name)
    db.add(user)
    db.flush()
    return user
