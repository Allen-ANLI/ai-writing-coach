"""Essay business logic.

Critical rule: creating an essay atomically creates the essay, its empty
working document, and the immutable original snapshot — all in one
transaction. There is no current_version_id; the working document is the live
content. Ownership is always taken from the authenticated user.
"""

import base64
import binascii
import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.essays import repository
from app.modules.essays.models import Essay, EssayVersion, EssayWorkingDocument
from app.modules.essays.schemas import CreateEssayRequest, PatchEssayRequest
from app.modules.users.models import User

EMPTY_DOCUMENT_JSON = {"type": "doc", "content": []}
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100


def _content_hash(plain_text: str) -> str:
    return hashlib.sha256(plain_text.encode("utf-8")).hexdigest()


def create_essay(db: Session, user: User, payload: CreateEssayRequest) -> Essay:
    now = utcnow()
    empty_hash = _content_hash("")

    essay = Essay(
        user_id=user.id,
        title=payload.title,
        writing_type=payload.writing_type,
        question_id=payload.question_id,
        status="active",
    )
    db.add(essay)
    db.flush()

    db.add(
        EssayWorkingDocument(
            essay_id=essay.id,
            content_json=EMPTY_DOCUMENT_JSON,
            plain_text="",
            word_count=0,
            server_revision=1,
            content_hash=empty_hash,
            last_saved_at=now,
            updated_at=now,
        )
    )
    original = EssayVersion(
        essay_id=essay.id,
        version_no=1,
        version_type="original",
        content_json=EMPTY_DOCUMENT_JSON,
        plain_text="",
        word_count=0,
        content_hash=empty_hash,
        source_revision=1,
        parent_version_id=None,
        created_by=user.id,
        created_at=now,
    )
    db.add(original)
    db.flush()

    essay.original_version_id = original.id
    essay.created_at = now
    essay.updated_at = now
    # One commit: essay + working document + original snapshot succeed or fail
    # together. Any flush error rolls the whole transaction back.
    db.commit()
    db.refresh(essay)
    return essay


def get_essay(db: Session, user: User, essay_id: uuid.UUID) -> Essay:
    essay = repository.get_for_user(db, essay_id, user.id)
    if essay is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Essay not found.")
    return essay


def update_essay(db: Session, user: User, essay_id: uuid.UUID, payload: PatchEssayRequest) -> Essay:
    essay = get_essay(db, user, essay_id)
    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates:
        essay.title = updates["title"]
    essay.updated_at = utcnow()
    db.commit()
    db.refresh(essay)
    return essay


def delete_essay(db: Session, user: User, essay_id: uuid.UUID) -> None:
    essay = get_essay(db, user, essay_id)
    repository.soft_delete(db, essay, utcnow())
    db.commit()


def _encode_cursor(essay: Essay) -> str:
    payload = {"t": essay.created_at.isoformat(), "i": str(essay.id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return datetime.fromisoformat(payload["t"]), uuid.UUID(payload["i"])
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise ApiError(422, "VALIDATION_ERROR", "Invalid pagination cursor.") from None


def list_essays(
    db: Session, user: User, *, limit: int, cursor: str | None
) -> tuple[list[Essay], str | None, int]:
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be between 1 and 100.")
    decoded = _decode_cursor(cursor) if cursor else None
    rows = repository.list_for_user(db, user.id, limit=limit, cursor=decoded)
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1]) if has_more and items else None
    return items, next_cursor, limit
