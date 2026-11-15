"""IELTS question bank queries. The published+licensed gate is enforced here."""

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session

from app.modules.ielts.models import (
    PERMITTED_LICENSES,
    IeltsQuestion,
    IeltsQuestionTag,
    QuestionTag,
    UserFavoriteQuestion,
)


def _permitted() -> Select:
    return select(IeltsQuestion).where(
        IeltsQuestion.is_published.is_(True),
        IeltsQuestion.license_status.in_(PERMITTED_LICENSES),
    )


def list_questions(
    db: Session,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
    task_type: str | None,
    topic: str | None,
    question_type: str | None,
) -> list[IeltsQuestion]:
    statement = _permitted()
    if task_type:
        statement = statement.where(IeltsQuestion.task_type == task_type)
    if question_type:
        statement = statement.where(IeltsQuestion.question_type == question_type)
    if topic:
        statement = (
            statement.join(IeltsQuestionTag, IeltsQuestionTag.question_id == IeltsQuestion.id)
            .join(QuestionTag, QuestionTag.id == IeltsQuestionTag.tag_id)
            .where(QuestionTag.slug == topic)
        )
    if cursor is not None:
        statement = statement.where(
            tuple_(IeltsQuestion.created_at, IeltsQuestion.id) < tuple_(cursor[0], cursor[1])
        )
    statement = statement.order_by(IeltsQuestion.created_at.desc(), IeltsQuestion.id.desc()).limit(
        limit + 1
    )
    return list(db.execute(statement).unique().scalars())


def get_question(db: Session, question_id: uuid.UUID) -> IeltsQuestion | None:
    return db.execute(_permitted().where(IeltsQuestion.id == question_id)).scalar_one_or_none()


def random_question(db: Session) -> IeltsQuestion | None:
    return db.execute(_permitted().order_by(func.random()).limit(1)).scalar_one_or_none()


def list_tags(db: Session) -> list[tuple[QuestionTag, int]]:
    statement = (
        select(QuestionTag, func.count(IeltsQuestion.id))
        .outerjoin(IeltsQuestionTag, IeltsQuestionTag.tag_id == QuestionTag.id)
        .outerjoin(
            IeltsQuestion,
            (IeltsQuestion.id == IeltsQuestionTag.question_id)
            & IeltsQuestion.is_published.is_(True)
            & IeltsQuestion.license_status.in_(PERMITTED_LICENSES),
        )
        .group_by(QuestionTag.id)
        .order_by(QuestionTag.name)
    )
    return [(tag, count) for tag, count in db.execute(statement).all()]


def favorited_ids(db: Session, user_id: uuid.UUID, question_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not question_ids:
        return set()
    rows = db.execute(
        select(UserFavoriteQuestion.question_id).where(
            UserFavoriteQuestion.user_id == user_id,
            UserFavoriteQuestion.question_id.in_(question_ids),
        )
    ).scalars()
    return set(rows)


def add_favorite(db: Session, user_id: uuid.UUID, question_id: uuid.UUID) -> None:
    existing = db.get(UserFavoriteQuestion, (user_id, question_id))
    if existing is None:
        db.add(UserFavoriteQuestion(user_id=user_id, question_id=question_id))


def remove_favorite(db: Session, user_id: uuid.UUID, question_id: uuid.UUID) -> None:
    existing = db.get(UserFavoriteQuestion, (user_id, question_id))
    if existing is not None:
        db.delete(existing)
