"""Data access for essays. Every query is scoped to the owning user;
soft-deleted essays are excluded everywhere."""

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session

from app.modules.essays.models import Essay, EssayVersion, EssayWorkingDocument


def _owned(user_id: uuid.UUID) -> Select:
    return select(Essay).where(Essay.user_id == user_id, Essay.deleted_at.is_(None))


def get_for_user(db: Session, essay_id: uuid.UUID, user_id: uuid.UUID) -> Essay | None:
    return db.execute(_owned(user_id).where(Essay.id == essay_id)).scalar_one_or_none()


def lock_working_document(db: Session, essay_id: uuid.UUID) -> EssayWorkingDocument:
    """Row-level lock serializing autosave / snapshot / restore per essay.

    populate_existing is required: get_essay may already have loaded this row
    via the joined relationship, and without it the locked re-read would keep
    the stale identity-map attributes (same trap the auth module documents).
    """
    return db.execute(
        select(EssayWorkingDocument)
        .where(EssayWorkingDocument.essay_id == essay_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def get_version_for_essay(
    db: Session, essay_id: uuid.UUID, version_id: uuid.UUID
) -> EssayVersion | None:
    return db.execute(
        select(EssayVersion).where(EssayVersion.essay_id == essay_id, EssayVersion.id == version_id)
    ).scalar_one_or_none()


def latest_version(db: Session, essay_id: uuid.UUID) -> EssayVersion | None:
    return db.execute(
        select(EssayVersion)
        .where(EssayVersion.essay_id == essay_id)
        .order_by(EssayVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def next_version_no(db: Session, essay_id: uuid.UUID) -> int:
    current = db.execute(
        select(func.max(EssayVersion.version_no)).where(EssayVersion.essay_id == essay_id)
    ).scalar_one()
    return (current or 0) + 1


def list_versions_for_essay(
    db: Session,
    essay_id: uuid.UUID,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
) -> list[EssayVersion]:
    query = select(EssayVersion).where(EssayVersion.essay_id == essay_id)
    if cursor is not None:
        query = query.where(
            tuple_(EssayVersion.created_at, EssayVersion.id) < tuple_(cursor[0], cursor[1])
        )
    query = query.order_by(EssayVersion.created_at.desc(), EssayVersion.id.desc()).limit(limit + 1)
    return list(db.execute(query).scalars())


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
