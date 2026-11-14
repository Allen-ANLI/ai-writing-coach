"""Data access for writing sessions; every query is owner-scoped."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.writing_sessions.models import WritingSession


def get_for_user(db: Session, session_id: uuid.UUID, user_id: uuid.UUID) -> WritingSession | None:
    return db.execute(
        select(WritingSession).where(
            WritingSession.id == session_id, WritingSession.user_id == user_id
        )
    ).scalar_one_or_none()


def active_for_essay(db: Session, essay_id: uuid.UUID) -> WritingSession | None:
    return db.execute(
        select(WritingSession).where(
            WritingSession.essay_id == essay_id, WritingSession.status == "active"
        )
    ).scalar_one_or_none()


def list_for_essay(db: Session, essay_id: uuid.UUID) -> list[WritingSession]:
    return list(
        db.execute(
            select(WritingSession)
            .where(WritingSession.essay_id == essay_id)
            .order_by(WritingSession.created_at.desc())
        ).scalars()
    )
