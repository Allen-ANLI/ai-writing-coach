"""Evaluation/rewrite business logic.

Queueing validates ownership and immutable-version binding, then persists a
queued row; the LLM work runs in a background task (processing.py) OUTSIDE
any request transaction. Acceptance is atomic and applies only server-stored
rewrite results (AGENTS §4: user-controlled acceptance, Original preserved).
"""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing import service as billing_service
from app.modules.essays import repository as essay_repository
from app.modules.essays import tiptap
from app.modules.essays.models import EssayEditEvent, EssayVersion
from app.modules.essays.service import get_essay
from app.modules.evaluations.models import EssayEvaluation, EssayRewrite
from app.modules.evaluations.schemas import (
    AcceptRewriteRequest,
    CreateEvaluationRequest,
    CreateRewriteRequest,
)
from app.modules.ielts import repository as ielts_repository
from app.modules.users.models import User


def queue_evaluation(
    db: Session, user: User, essay_id: uuid.UUID, payload: CreateEvaluationRequest
) -> EssayEvaluation:
    essay = get_essay(db, user, essay_id)
    version = essay_repository.get_version_for_essay(db, essay_id, payload.version_id)
    if version is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Version not found for this essay.")

    if payload.evaluation_type == "ielts":
        if payload.task_type is None:
            raise ApiError(422, "VALIDATION_ERROR", "task_type is required for IELTS evaluation.")
        if essay.question_id is not None:
            question = ielts_repository.get_question(db, essay.question_id)
            if question is not None and question.task_type != payload.task_type:
                raise ApiError(
                    422, "VALIDATION_ERROR", "task_type does not match the essay's question."
                )
    elif payload.task_type is not None:
        raise ApiError(422, "VALIDATION_ERROR", "task_type only applies to IELTS evaluation.")

    billing_service.guard_evaluation(db, user.id)
    billing_service.guard_ai_call(db, user.id)
    billing_service.meter_evaluation(db, user.id)
    evaluation = EssayEvaluation(
        essay_id=essay.id,
        version_id=version.id,
        user_id=user.id,
        evaluation_type=payload.evaluation_type,
        task_type=payload.task_type,
        status="queued",
        created_at=utcnow(),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def list_evaluations(db: Session, user: User, essay_id: uuid.UUID) -> list[EssayEvaluation]:
    get_essay(db, user, essay_id)
    rows = db.execute(
        select(EssayEvaluation)
        .where(EssayEvaluation.essay_id == essay_id, EssayEvaluation.user_id == user.id)
        .order_by(EssayEvaluation.created_at.desc(), EssayEvaluation.id.desc())
    ).scalars()
    return list(rows)


def get_evaluation(db: Session, user: User, evaluation_id: uuid.UUID) -> EssayEvaluation:
    evaluation = db.execute(
        select(EssayEvaluation).where(
            EssayEvaluation.id == evaluation_id, EssayEvaluation.user_id == user.id
        )
    ).scalar_one_or_none()
    if evaluation is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Evaluation not found.")
    return evaluation


def delete_evaluation(db: Session, user: User, evaluation_id: uuid.UUID) -> None:
    evaluation = get_evaluation(db, user, evaluation_id)
    db.delete(evaluation)
    db.commit()


def queue_rewrite(
    db: Session, user: User, evaluation_id: uuid.UUID, payload: CreateRewriteRequest
) -> EssayRewrite:
    evaluation = get_evaluation(db, user, evaluation_id)
    if evaluation.status != "completed":
        raise ApiError(409, "VALIDATION_ERROR", "Only completed evaluations can be rewritten.")
    billing_service.guard_ai_call(db, user.id)
    rewrite = EssayRewrite(
        evaluation_id=evaluation.id,
        source_version_id=evaluation.version_id,
        modification_level=payload.modification_level,
        status="queued",
        created_at=utcnow(),
    )
    db.add(rewrite)
    db.commit()
    db.refresh(rewrite)
    return rewrite


def get_rewrite(db: Session, user: User, rewrite_id: uuid.UUID) -> EssayRewrite:
    rewrite = db.execute(
        select(EssayRewrite)
        .join(EssayEvaluation, EssayEvaluation.id == EssayRewrite.evaluation_id)
        .where(EssayRewrite.id == rewrite_id, EssayEvaluation.user_id == user.id)
    ).scalar_one_or_none()
    if rewrite is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Rewrite not found.")
    return rewrite


def accept_rewrite(
    db: Session, user: User, rewrite_id: uuid.UUID, payload: AcceptRewriteRequest
) -> tuple[EssayRewrite, EssayVersion, int]:
    """Atomically apply the server-stored rewrite: working document update +
    ai_rewrite version + result_version_id + edit event. 409 on revision
    conflict or duplicate acceptance; the client never supplies content."""
    rewrite = get_rewrite(db, user, rewrite_id)
    if rewrite.status != "completed" or rewrite.result_content_json is None:
        raise ApiError(409, "VALIDATION_ERROR", "This rewrite is not ready to accept.")
    if rewrite.result_version_id is not None:
        raise ApiError(409, "VALIDATION_ERROR", "This rewrite was already accepted.")
    evaluation = get_evaluation(db, user, rewrite.evaluation_id)
    essay = get_essay(db, user, evaluation.essay_id)

    document = essay_repository.lock_working_document(db, essay.id)
    if payload.base_revision != document.server_revision:
        raise ApiError(
            409, "WORKING_DOCUMENT_CONFLICT", "The working document changed; reload and retry."
        )

    now = utcnow()
    before_text = document.plain_text
    from_revision = document.server_revision
    plain_text = rewrite.result_plain_text or ""
    document.content_json = rewrite.result_content_json
    document.plain_text = plain_text
    document.word_count = tiptap.count_words(plain_text)
    document.content_hash = hashlib.sha256(plain_text.encode("utf-8")).hexdigest()
    document.server_revision += 1
    document.last_saved_at = now
    document.updated_at = now
    essay.updated_at = now

    version = EssayVersion(
        essay_id=essay.id,
        version_no=essay_repository.next_version_no(db, essay.id),
        version_type="ai_rewrite",
        label=f"AI rewrite ({rewrite.modification_level})",
        content_json=rewrite.result_content_json,
        plain_text=plain_text,
        word_count=document.word_count,
        content_hash=document.content_hash,
        source_revision=document.server_revision,
        parent_version_id=rewrite.source_version_id,
        created_by=user.id,
        created_at=now,
    )
    db.add(version)
    db.flush()
    rewrite.result_version_id = version.id
    db.add(
        EssayEditEvent(
            essay_id=essay.id,
            from_version_id=rewrite.source_version_id,
            to_version_id=version.id,
            from_server_revision=from_revision,
            to_server_revision=document.server_revision,
            rewrite_id=rewrite.id,
            actor_type="ai_accept",
            event_type="accept_rewrite",
            before_text=before_text,
            after_text=plain_text,
            event_metadata={"modification_level": rewrite.modification_level},
            created_at=now,
        )
    )
    db.commit()
    db.refresh(document)
    return rewrite, version, document.server_revision
