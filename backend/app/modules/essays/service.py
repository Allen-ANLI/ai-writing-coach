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
from app.modules.essays import repository, tiptap
from app.modules.essays.models import Essay, EssayEditEvent, EssayVersion, EssayWorkingDocument
from app.modules.essays.schemas import (
    CreateEssayRequest,
    CreateSnapshotRequest,
    PatchEssayRequest,
    RestoreRequest,
    SaveWorkingDocumentRequest,
)
from app.modules.ielts import repository as ielts_repository
from app.modules.users.models import User

EMPTY_DOCUMENT_JSON = {"type": "doc", "content": []}
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100


def _content_hash(plain_text: str) -> str:
    return hashlib.sha256(plain_text.encode("utf-8")).hexdigest()


def create_essay(db: Session, user: User, payload: CreateEssayRequest) -> Essay:
    now = utcnow()
    empty_hash = _content_hash("")

    question_prompt = payload.question_prompt
    if payload.question_id is not None:
        question = ielts_repository.get_question(db, payload.question_id)
        if question is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Question not found.")
        expected_type = "ielts_task1" if question.task_type == "task1" else "ielts_task2"
        if payload.writing_type != expected_type:
            raise ApiError(
                422, "VALIDATION_ERROR", f"writing_type must be {expected_type} for this question."
            )
        if question_prompt is None:
            question_prompt = question.prompt_text

    essay = Essay(
        user_id=user.id,
        title=payload.title,
        writing_type=payload.writing_type,
        question_id=payload.question_id,
        question_prompt=question_prompt,
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
    if "question_prompt" in updates:
        essay.question_prompt = updates["question_prompt"]
    essay.updated_at = utcnow()
    db.commit()
    db.refresh(essay)
    return essay


def delete_essay(db: Session, user: User, essay_id: uuid.UUID) -> None:
    essay = get_essay(db, user, essay_id)
    repository.soft_delete(db, essay, utcnow())
    db.commit()


def _encode_cursor(item: Essay | EssayVersion) -> str:
    payload = {"t": item.created_at.isoformat(), "i": str(item.id)}
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


# --- Slice 2B: Working Document, snapshots, versions, restore ---


def _check_revision(document: EssayWorkingDocument, base_revision: int) -> None:
    if document.server_revision != base_revision:
        raise ApiError(
            409,
            "WORKING_DOCUMENT_CONFLICT",
            "The working document changed since your last save.",
            [
                {
                    "field": "base_revision",
                    "reason": f"current server_revision is {document.server_revision}",
                }
            ],
        )


def get_working_document(db: Session, user: User, essay_id: uuid.UUID) -> EssayWorkingDocument:
    get_essay(db, user, essay_id)
    return repository.lock_working_document(db, essay_id)


def save_working_document(
    db: Session, user: User, essay_id: uuid.UUID, payload: SaveWorkingDocumentRequest
) -> EssayWorkingDocument:
    """Autosave: optimistic concurrency on base_revision, server-derived text
    and word count, revision increment, NO snapshot (ERD §6.2, API Spec §4.2)."""
    essay = get_essay(db, user, essay_id)
    document = repository.lock_working_document(db, essay_id)
    _check_revision(document, payload.base_revision)

    content_json = tiptap.validate_document(payload.content_json)
    plain_text, word_count = tiptap.derive_text(content_json)
    tiptap.check_client_values(payload.plain_text, payload.word_count, plain_text, word_count)

    now = utcnow()
    document.content_json = content_json
    document.plain_text = plain_text
    document.word_count = word_count
    document.server_revision += 1
    document.content_hash = _content_hash(plain_text)
    document.last_saved_at = now
    document.updated_at = now
    essay.updated_at = now
    db.commit()
    db.refresh(document)
    return document


def create_snapshot(
    db: Session, user: User, essay_id: uuid.UUID, payload: CreateSnapshotRequest
) -> EssayVersion:
    """Immutable snapshot of the current revision. Only Issues whose
    source_server_revision exactly matches may be archived (ERD §15.2); the
    writing_issues table arrives with the Grammar slice, which extends this
    function — until then there are no issues to archive."""
    essay = get_essay(db, user, essay_id)
    document = repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.source_revision:
        raise ApiError(
            409,
            "DOCUMENT_VERSION_CONFLICT",
            "Snapshots must capture the current working document revision.",
            [
                {
                    "field": "source_revision",
                    "reason": f"current server_revision is {document.server_revision}",
                }
            ],
        )

    parent = repository.latest_version(db, essay_id)
    version = EssayVersion(
        essay_id=essay_id,
        version_no=repository.next_version_no(db, essay_id),
        version_type=payload.version_type,
        label=payload.label,
        content_json=document.content_json,
        plain_text=document.plain_text,
        word_count=document.word_count,
        content_hash=document.content_hash,
        source_revision=document.server_revision,
        parent_version_id=parent.id if parent else None,
        created_by=user.id,
        created_at=utcnow(),
    )
    db.add(version)
    essay.updated_at = utcnow()
    db.commit()
    db.refresh(version)
    return version


def list_versions(
    db: Session, user: User, essay_id: uuid.UUID, *, limit: int, cursor: str | None
) -> tuple[list[EssayVersion], str | None, int]:
    get_essay(db, user, essay_id)
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be between 1 and 100.")
    decoded = _decode_cursor(cursor) if cursor else None
    rows = repository.list_versions_for_essay(db, essay_id, limit=limit, cursor=decoded)
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1]) if has_more and items else None
    return items, next_cursor, limit


def get_version(
    db: Session, user: User, essay_id: uuid.UUID, version_id: uuid.UUID
) -> EssayVersion:
    get_essay(db, user, essay_id)
    version = repository.get_version_for_essay(db, essay_id, version_id)
    if version is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Version not found.")
    return version


def restore_version(
    db: Session, user: User, essay_id: uuid.UUID, payload: RestoreRequest
) -> tuple[EssayWorkingDocument, EssayVersion]:
    """Copy a snapshot into the Working Document atomically: revision
    increment + Edit Event; the source snapshot is never modified (AGENTS §4)."""
    essay = get_essay(db, user, essay_id)
    version = repository.get_version_for_essay(db, essay_id, payload.version_id)
    if version is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Version not found.")
    document = repository.lock_working_document(db, essay_id)
    _check_revision(document, payload.base_revision)

    now = utcnow()
    before_text = document.plain_text
    from_revision = document.server_revision
    document.content_json = version.content_json
    document.plain_text = version.plain_text
    document.word_count = version.word_count
    document.content_hash = version.content_hash
    document.server_revision += 1
    document.last_saved_at = now
    document.updated_at = now
    essay.updated_at = now
    db.add(
        EssayEditEvent(
            essay_id=essay_id,
            from_version_id=version.id,
            to_version_id=None,
            from_server_revision=from_revision,
            to_server_revision=document.server_revision,
            actor_type="user",
            event_type="restore",
            before_text=before_text,
            after_text=version.plain_text,
            event_metadata={"restored_version_id": str(version.id)},
            created_at=now,
        )
    )
    db.commit()
    db.refresh(document)
    return document, version
