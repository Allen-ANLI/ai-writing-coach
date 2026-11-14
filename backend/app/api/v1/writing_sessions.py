"""Writing session routes (thin). Identity from auth context; sessions are
owner-scoped and foreign resources return 404. Feature flags are always
server-derived from the session mode."""

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.idempotency import payload_hash, run_idempotent
from app.infrastructure.database import get_db
from app.modules.users.models import User
from app.modules.writing_sessions import service
from app.modules.writing_sessions.models import WritingSession
from app.modules.writing_sessions.schemas import (
    CreateSessionRequest,
    PatchSessionRequest,
    SessionListResponse,
    SessionResponse,
    SubmitResponse,
    SubmitSessionRequest,
)
from app.schemas.common import new_request_id

router = APIRouter()


def _session_data(session: WritingSession) -> dict:
    data = {
        field: getattr(session, field)
        for field in (
            "id",
            "essay_id",
            "mode",
            "activity_type",
            "exam_config",
            "started_at",
            "deadline_at",
            "submitted_at",
            "status",
            "created_at",
        )
    }
    data["enabled_features"] = service.enabled_features(session.mode).model_dump()
    return data


def _session_response(session: WritingSession) -> SessionResponse:
    return SessionResponse.model_validate(
        {"data": _session_data(session), "meta": {"request_id": new_request_id()}}
    )


@router.post("/essays/{essay_id}/sessions", status_code=201, response_model=SessionResponse)
def create_session(
    essay_id: uuid.UUID,
    payload: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    return _session_response(service.create_session(db, user, essay_id, payload))


@router.get("/essays/{essay_id}/sessions", response_model=SessionListResponse)
def list_sessions(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    sessions = service.list_sessions(db, user, essay_id)
    return SessionListResponse.model_validate(
        {
            "data": {"items": [_session_data(session) for session in sessions]},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/writing-sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    return _session_response(service.get_session(db, user, session_id))


@router.patch("/writing-sessions/{session_id}", response_model=SessionResponse)
def patch_session(
    session_id: uuid.UUID,
    payload: PatchSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    return _session_response(service.patch_session(db, user, session_id, payload))


@router.post("/writing-sessions/{session_id}/submit", status_code=201)
def submit_session(
    session_id: uuid.UUID,
    payload: SubmitSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> JSONResponse:
    def operation() -> JSONResponse:
        session, final_version, shared_original = service.submit_session(
            db, user, session_id, payload
        )
        body = SubmitResponse.model_validate(
            {
                "data": {
                    "session_id": session.id,
                    "status": session.status,
                    "submitted_at": session.submitted_at,
                    "final_version_id": final_version.id,
                    "server_revision": final_version.source_revision,
                    "shared_original": shared_original,
                },
                "meta": {"request_id": new_request_id()},
            }
        )
        return JSONResponse(status_code=201, content=body.model_dump(mode="json"))

    return run_idempotent(
        db,
        user.id,
        idempotency_key,
        method="POST",
        path=f"/writing-sessions/{session_id}/submit",
        request_hash=payload_hash(payload.model_dump_json()),
        operation=operation,
    )
