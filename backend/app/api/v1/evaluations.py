"""Evaluation/rewrite routes (thin). Queueing returns 202; the LLM work runs
in a background task using the app's session factory."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.idempotency import payload_hash, run_idempotent
from app.infrastructure.database import get_db
from app.modules.evaluations import processing, service
from app.modules.evaluations.schemas import (
    AcceptRewriteRequest,
    AcceptRewriteResponse,
    CreateEvaluationRequest,
    CreateRewriteRequest,
    EvaluationListResponse,
    EvaluationQueuedResponse,
    EvaluationResponse,
    RewriteQueuedResponse,
    RewriteResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


@router.post("/essays/{essay_id}/evaluations", status_code=202)
def queue_evaluation(
    essay_id: uuid.UUID,
    payload: CreateEvaluationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> JSONResponse:
    def operation() -> JSONResponse:
        evaluation = service.queue_evaluation(db, user, essay_id, payload)
        background_tasks.add_task(
            processing.process_evaluation, request.app.state.session_factory, evaluation.id
        )
        body = EvaluationQueuedResponse.model_validate(
            {
                "data": {"evaluation_id": evaluation.id, "status": evaluation.status},
                "meta": {"request_id": new_request_id()},
            }
        )
        return JSONResponse(status_code=202, content=body.model_dump(mode="json"))

    return run_idempotent(
        db,
        user.id,
        idempotency_key,
        method="POST",
        path=f"/essays/{essay_id}/evaluations",
        request_hash=payload_hash(payload.model_dump_json()),
        operation=operation,
    )


@router.get("/essays/{essay_id}/evaluations", response_model=EvaluationListResponse)
def list_evaluations(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationListResponse:
    items = service.list_evaluations(db, user, essay_id)
    return EvaluationListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(
    evaluation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationResponse:
    evaluation = service.get_evaluation(db, user, evaluation_id)
    return EvaluationResponse.model_validate(
        {"data": evaluation, "meta": {"request_id": new_request_id()}}
    )


@router.delete("/evaluations/{evaluation_id}", status_code=204)
def delete_evaluation(
    evaluation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_evaluation(db, user, evaluation_id)
    return Response(status_code=204)


@router.post("/evaluations/{evaluation_id}/rewrite", status_code=202)
def queue_rewrite(
    evaluation_id: uuid.UUID,
    payload: CreateRewriteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> JSONResponse:
    def operation() -> JSONResponse:
        rewrite = service.queue_rewrite(db, user, evaluation_id, payload)
        background_tasks.add_task(
            processing.process_rewrite, request.app.state.session_factory, rewrite.id
        )
        body = RewriteQueuedResponse.model_validate(
            {
                "data": {"rewrite_id": rewrite.id, "status": rewrite.status},
                "meta": {"request_id": new_request_id()},
            }
        )
        return JSONResponse(status_code=202, content=body.model_dump(mode="json"))

    return run_idempotent(
        db,
        user.id,
        idempotency_key,
        method="POST",
        path=f"/evaluations/{evaluation_id}/rewrite",
        request_hash=payload_hash(payload.model_dump_json()),
        operation=operation,
    )


@router.get("/rewrites/{rewrite_id}", response_model=RewriteResponse)
def get_rewrite(
    rewrite_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RewriteResponse:
    rewrite = service.get_rewrite(db, user, rewrite_id)
    return RewriteResponse.model_validate(
        {"data": rewrite, "meta": {"request_id": new_request_id()}}
    )


@router.post("/rewrites/{rewrite_id}/accept")
def accept_rewrite(
    rewrite_id: uuid.UUID,
    payload: AcceptRewriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> JSONResponse:
    def operation() -> JSONResponse:
        rewrite, version, server_revision = service.accept_rewrite(db, user, rewrite_id, payload)
        body = AcceptRewriteResponse.model_validate(
            {
                "data": {
                    "rewrite_id": rewrite.id,
                    "result_version_id": version.id,
                    "server_revision": server_revision,
                    "word_count": version.word_count,
                },
                "meta": {"request_id": new_request_id()},
            }
        )
        return JSONResponse(status_code=200, content=body.model_dump(mode="json"))

    return run_idempotent(
        db,
        user.id,
        idempotency_key,
        method="POST",
        path=f"/rewrites/{rewrite_id}/accept",
        request_hash=payload_hash(payload.model_dump_json()),
        operation=operation,
    )
