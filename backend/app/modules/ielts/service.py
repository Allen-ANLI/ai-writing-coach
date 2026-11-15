"""IELTS question bank service: listing, detail, random, tags, favorites."""

import base64
import binascii
import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.modules.ielts import repository
from app.modules.ielts.models import IeltsQuestion
from app.modules.ielts.schemas import QuestionDetail, QuestionSummary, TagCount, TagRef
from app.modules.users.models import User

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100


def _encode_cursor(item: IeltsQuestion) -> str:
    payload = {"t": item.created_at.isoformat(), "i": str(item.id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return datetime.fromisoformat(payload["t"]), uuid.UUID(payload["i"])
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise ApiError(422, "VALIDATION_ERROR", "Invalid pagination cursor.") from None


def _summary(question: IeltsQuestion, favorited: set[uuid.UUID]) -> QuestionSummary:
    return QuestionSummary(
        id=question.id,
        task_type=question.task_type,
        question_type=question.question_type,
        prompt_text=question.prompt_text,
        prompt_translation=question.prompt_translation,
        difficulty=question.difficulty,
        tags=[TagRef(id=tag.id, name=tag.name, slug=tag.slug) for tag in question.tags],
        is_favorited=question.id in favorited,
        created_at=question.created_at,
    )


def _detail(question: IeltsQuestion, favorited: set[uuid.UUID]) -> QuestionDetail:
    return QuestionDetail(
        **_summary(question, favorited).model_dump(),
        source_type=question.source_type,
        source_title=question.source_title,
        license_status=question.license_status,
    )


def list_questions(
    db: Session,
    user: User,
    *,
    limit: int,
    cursor: str | None,
    task_type: str | None,
    topic: str | None,
    question_type: str | None,
) -> tuple[list[QuestionSummary], str | None, int]:
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be between 1 and 100.")
    decoded = _decode_cursor(cursor) if cursor else None
    rows = repository.list_questions(
        db,
        limit=limit,
        cursor=decoded,
        task_type=task_type,
        topic=topic,
        question_type=question_type,
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    favorited = repository.favorited_ids(db, user.id, [q.id for q in items])
    next_cursor = _encode_cursor(items[-1]) if has_more and items else None
    return [_summary(q, favorited) for q in items], next_cursor, limit


def get_question(db: Session, user: User, question_id: uuid.UUID) -> QuestionDetail:
    question = repository.get_question(db, question_id)
    if question is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Question not found.")
    favorited = repository.favorited_ids(db, user.id, [question.id])
    return _detail(question, favorited)


def random_question(db: Session, user: User) -> QuestionDetail:
    question = repository.random_question(db)
    if question is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "No questions available.")
    favorited = repository.favorited_ids(db, user.id, [question.id])
    return _detail(question, favorited)


def list_tags(db: Session) -> list[TagCount]:
    return [
        TagCount(id=tag.id, name=tag.name, slug=tag.slug, question_count=count)
        for tag, count in repository.list_tags(db)
    ]


def favorite_question(db: Session, user: User, question_id: uuid.UUID) -> None:
    if repository.get_question(db, question_id) is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Question not found.")
    repository.add_favorite(db, user.id, question_id)
    db.commit()


def unfavorite_question(db: Session, user: User, question_id: uuid.UUID) -> None:
    if repository.get_question(db, question_id) is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Question not found.")
    repository.remove_favorite(db, user.id, question_id)
    db.commit()
