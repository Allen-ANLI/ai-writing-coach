"""Writing session business logic (API Spec §5, SD §10).

- Exactly two modes; enabled_features is always derived server-side.
- One active session per essay; history is kept.
- Submit is atomic: revision check, Final Snapshot (shared with Original when
  content is identical), essay pointer, session state, Edit Event.
"""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.essays import repository as essay_repository
from app.modules.essays.models import EssayEditEvent, EssayVersion
from app.modules.essays.service import get_essay
from app.modules.users.models import User
from app.modules.writing_sessions import repository
from app.modules.writing_sessions.models import WritingSession
from app.modules.writing_sessions.schemas import (
    CreateSessionRequest,
    EnabledFeatures,
    PatchSessionRequest,
    SubmitSessionRequest,
)


def enabled_features(mode: str) -> EnabledFeatures:
    assisted = mode == "assisted"
    return EnabledFeatures(
        realtime_grammar=assisted,
        llm_assistance=assisted,
        chinese_to_english=assisted,
        expression_recommendations=assisted,
        ghost_text=assisted,
        paragraph_analysis=assisted,
        autosave=True,
        post_submission_evaluation=True,
    )


def _deadline(session: WritingSession) -> None:
    if session.activity_type == "mock_exam" and session.exam_config:
        minutes = session.exam_config.get("duration_minutes")
        if isinstance(minutes, int):
            session.deadline_at = session.started_at + timedelta(minutes=minutes)


def create_session(
    db: Session, user: User, essay_id: uuid.UUID, payload: CreateSessionRequest
) -> WritingSession:
    get_essay(db, user, essay_id)
    if payload.activity_type == "mock_exam":
        if payload.exam_config is None:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "mock_exam sessions require exam_config.",
                [{"field": "exam_config", "reason": "required for mock_exam"}],
            )
    elif payload.exam_config is not None:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "exam_config is only valid for mock_exam sessions.",
            [{"field": "exam_config", "reason": "only valid for mock_exam"}],
        )
    if repository.active_for_essay(db, essay_id) is not None:
        raise ApiError(
            409, "RESOURCE_ALREADY_EXISTS", "This essay already has an active writing session."
        )

    now = utcnow()
    session = WritingSession(
        essay_id=essay_id,
        user_id=user.id,
        mode=payload.mode,
        activity_type=payload.activity_type,
        exam_config=payload.exam_config.model_dump() if payload.exam_config else None,
        started_at=now,
        status="active",
        created_at=now,
    )
    _deadline(session)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, user: User, session_id: uuid.UUID) -> WritingSession:
    session = repository.get_for_user(db, session_id, user.id)
    if session is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Writing session not found.")
    return session


def list_sessions(db: Session, user: User, essay_id: uuid.UUID) -> list[WritingSession]:
    get_essay(db, user, essay_id)
    return repository.list_for_essay(db, essay_id)


def patch_session(
    db: Session, user: User, session_id: uuid.UUID, payload: PatchSessionRequest
) -> WritingSession:
    session = get_session(db, user, session_id)
    if session.status != "active":
        raise ApiError(400, "VALIDATION_ERROR", "Only active sessions can be updated.")
    updates = payload.model_dump(exclude_unset=True)
    if "exam_config" in updates:
        if session.activity_type != "mock_exam":
            raise ApiError(
                422, "VALIDATION_ERROR", "exam_config is only valid for mock_exam sessions."
            )
        session.exam_config = updates["exam_config"]
        _deadline(session)
    if updates.get("status") == "cancelled":
        session.status = "cancelled"
    db.commit()
    db.refresh(session)
    return session


def submit_session(
    db: Session, user: User, session_id: uuid.UUID, payload: SubmitSessionRequest
) -> tuple[WritingSession, EssayVersion, bool]:
    """Atomic submit. Returns (session, final_version, shared_original)."""
    session = get_session(db, user, session_id)
    if session.status != "active":
        raise ApiError(400, "VALIDATION_ERROR", "Only active sessions can be submitted.")
    now = utcnow()
    if session.deadline_at is not None and now > session.deadline_at:
        raise ApiError(400, "VALIDATION_ERROR", "The exam time limit has elapsed.")

    essay = get_essay(db, user, session.essay_id)
    document = essay_repository.lock_working_document(db, session.essay_id)
    if document.server_revision != payload.expected_server_revision:
        raise ApiError(
            409,
            "WORKING_DOCUMENT_CONFLICT",
            "The working document changed; save before submitting.",
            [
                {
                    "field": "expected_server_revision",
                    "reason": f"current server_revision is {document.server_revision}",
                }
            ],
        )

    original = essay_repository.get_version_for_essay(
        db, session.essay_id, essay.original_version_id
    )
    shared_original = original is not None and original.content_hash == document.content_hash
    if shared_original:
        final_version = original
    else:
        parent = essay_repository.latest_version(db, session.essay_id)
        final_version = EssayVersion(
            essay_id=session.essay_id,
            version_no=essay_repository.next_version_no(db, session.essay_id),
            version_type="final",
            label=None,
            content_json=document.content_json,
            plain_text=document.plain_text,
            word_count=document.word_count,
            content_hash=document.content_hash,
            source_revision=document.server_revision,
            parent_version_id=parent.id if parent else None,
            created_by=user.id,
            created_at=now,
        )
        db.add(final_version)
        db.flush()

    essay.final_version_id = final_version.id
    essay.updated_at = now
    session.status = "submitted"
    session.submitted_at = now
    db.add(
        EssayEditEvent(
            essay_id=session.essay_id,
            from_version_id=None,
            to_version_id=final_version.id,
            from_server_revision=document.server_revision,
            to_server_revision=document.server_revision,
            actor_type="user",
            event_type="submit",
            before_text=document.plain_text,
            after_text=document.plain_text,
            event_metadata={
                "session_id": str(session.id),
                "shared_original": shared_original,
            },
            created_at=now,
        )
    )
    db.commit()
    db.refresh(session)
    db.refresh(final_version)
    return session, final_version, shared_original
