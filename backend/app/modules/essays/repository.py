"""Data access for essays. Every query is scoped to the owning user;
soft-deleted essays are excluded everywhere."""

import uuid
from datetime import datetime

from sqlalchemy import Select, select, tuple_
from sqlalchemy.orm import Session

from app.modules.essays.models import Essay


def _owned(user_id: uuid.UUID) -> Select:
    return select(Essay).where(Essay.user_id == user_id, Essay.deleted_at.is_(None))


def get_for_user(db: Session, essay_id: uuid.UUID, user_id: uuid.UUID) -> Essay | None:
    return db.execute(_owned(user_id).where(Essay.id == essay_id)).scalar_one_or_none()


def list_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
) -> list[Essay]:
    query = _owned(user_id)
    if cursor is not None:
        query = query.where(tuple_(Essay.created_at, Essay.id) < tuple_(cursor[0], cursor[1]))
    query = query.order_by(Essay.created_at.desc(), Essay.id.desc()).limit(limit + 1)
    return list(db.execute(query).scalars())


def soft_delete(db: Session, essay: Essay, now: datetime) -> None:
    essay.deleted_at = now
