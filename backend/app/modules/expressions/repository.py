"""Data access for expressions; every query is owner-scoped."""

import uuid
from datetime import datetime

from sqlalchemy import Select, func, or_, select, tuple_
from sqlalchemy.orm import Session

from app.modules.expressions.models import (
    ExpressionSuggestion,
    ExpressionSuggestionItem,
    UserExpression,
)


def _owned(user_id: uuid.UUID) -> Select:
    return select(UserExpression).where(
        UserExpression.user_id == user_id, UserExpression.deleted_at.is_(None)
    )


def get_for_user(
    db: Session, expression_id: uuid.UUID, user_id: uuid.UUID
) -> UserExpression | None:
    return db.execute(
        _owned(user_id).where(UserExpression.id == expression_id)
    ).scalar_one_or_none()


def list_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
    status: str | None,
    topic: str | None,
    query: str | None,
) -> list[UserExpression]:
    statement = _owned(user_id)
    if status:
        statement = statement.where(UserExpression.status == status)
    if topic:
        statement = statement.where(UserExpression.topic == topic)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            or_(
                UserExpression.english_text.ilike(pattern),
                UserExpression.chinese_meaning.ilike(pattern),
            )
        )
    if cursor is not None:
        statement = statement.where(
            tuple_(UserExpression.created_at, UserExpression.id) < tuple_(cursor[0], cursor[1])
        )
    statement = statement.order_by(
        UserExpression.created_at.desc(), UserExpression.id.desc()
    ).limit(limit + 1)
    return list(db.execute(statement).scalars())


def find_duplicates(db: Session, user_id: uuid.UUID, english_text: str) -> UserExpression | None:
    return db.execute(
        _owned(user_id).where(func.lower(UserExpression.english_text) == english_text.lower())
    ).scalar_one_or_none()


def keyword_candidates(
    db: Session, user_id: uuid.UUID, text: str, *, limit: int = 5
) -> list[UserExpression]:
    """Keyword recall from the user's own knowledge base (previously-learned).

    Semantic pgvector retrieval arrives with the RAG slice; contextual
    suitability is still judged by the LLM before recommending.
    """
    words = [w for w in text.lower().split() if len(w) > 3][:6]
    if not words:
        return []
    conditions = [UserExpression.english_text.ilike(f"%{w}%") for w in words]
    statement = (
        _owned(user_id)
        .where(UserExpression.status != "archived")
        .where(or_(*conditions))
        .order_by(UserExpression.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars())


def get_suggestion_for_user(
    db: Session, suggestion_id: uuid.UUID, user_id: uuid.UUID
) -> ExpressionSuggestion | None:
    return db.execute(
        select(ExpressionSuggestion).where(
            ExpressionSuggestion.id == suggestion_id,
            ExpressionSuggestion.user_id == user_id,
        )
    ).scalar_one_or_none()


def get_item_for_suggestion(
    db: Session, suggestion_id: uuid.UUID, item_id: uuid.UUID
) -> ExpressionSuggestionItem | None:
    return db.execute(
        select(ExpressionSuggestionItem).where(
            ExpressionSuggestionItem.id == item_id,
            ExpressionSuggestionItem.suggestion_id == suggestion_id,
        )
    ).scalar_one_or_none()
