"""Essay routes (thin). Identity always comes from the auth context; essays
are scoped to the authenticated user and foreign resources return 404."""

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.idempotency import payload_hash, run_idempotent
from app.infrastructure.database import get_db
from app.modules.essays import service
from app.modules.essays.schemas import (
    CreateEssayRequest,
    CreateSnapshotRequest,
    EssayListResponse,
    EssayResponse,
    PatchEssayRequest,
    RestoreRequest,
    RestoreResponse,
    SaveWorkingDocumentRequest,
    VersionListResponse,
    VersionResponse,
    WorkingDocumentResponse,
    WorkingDocumentSavedResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


def _essay_response(essay) -> EssayResponse:
    return EssayResponse.model_validate({"data": essay, "meta": {"request_id": new_request_id()}})


@router.post("/essays", status_code=201, response_model=EssayResponse)
def create_essay(
    payload: CreateEssayRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> EssayResponse:
    # Idempotency-Key is accepted per contract; deduplication storage arrives
    # with a later slice (documented reservation, no silent semantic change).
    essay = service.create_essay(db, user, payload)
    return _essay_response(essay)


@router.get("/essays", response_model=EssayListResponse)
def list_essays(
    limit: int = Query(default=service.DEFAULT_LIST_LIMIT, ge=1, le=service.MAX_LIST_LIMIT),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EssayListResponse:
    items, next_cursor, applied_limit = service.list_essays(db, user, limit=limit, cursor=cursor)
    return EssayListResponse.model_validate(
        {
            "data": {"items": items, "next_cursor": next_cursor, "limit": applied_limit},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/essays/{essay_id}", response_model=EssayResponse)
def get_essay(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EssayResponse:
    return _essay_response(service.get_essay(db, user, essay_id))


@router.patch("/essays/{essay_id}", response_model=EssayResponse)
def patch_essay(
    essay_id: uuid.UUID,
    payload: PatchEssayRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EssayResponse:
    return _essay_response(service.update_essay(db, user, essay_id, payload))


@router.delete("/essays/{essay_id}", status_code=204)
def delete_essay(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_essay(db, user, essay_id)
    return Response(status_code=204)


# --- Slice 2B: Working Document, snapshots, versions, restore ---


@router.get("/essays/{essay_id}/working-document", response_model=WorkingDocumentResponse)
def get_working_document(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkingDocumentResponse:
    document = service.get_working_document(db, user, essay_id)
    return WorkingDocumentResponse.model_validate(
        {"data": document, "meta": {"request_id": new_request_id()}}
    )


@router.put("/essays/{essay_id}/working-document", response_model=WorkingDocumentSavedResponse)
def save_working_document(
    essay_id: uuid.UUID,
    payload: SaveWorkingDocumentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkingDocumentSavedResponse:
    document = service.save_working_document(db, user, essay_id, payload)
    return WorkingDocumentSavedResponse.model_validate(
        {
            "data": {
                "essay_id": essay_id,
                "server_revision": document.server_revision,
                "client_revision": payload.client_revision,
                "saved": True,
                "saved_at": document.last_saved_at,
            },
            "meta": {"request_id": new_request_id()},
        }
    )


@router.post("/essays/{essay_id}/snapshots", status_code=201)
def create_snapshot(
    essay_id: uuid.UUID,
    payload: CreateSnapshotRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> JSONResponse:
    def operation() -> JSONResponse:
        version = service.create_snapshot(db, user, essay_id, payload)
        body = VersionResponse.model_validate(
            {"data": version, "meta": {"request_id": new_request_id()}}
        )
        return JSONResponse(status_code=201, content=body.model_dump(mode="json"))

    return run_idempotent(
        db,
        user.id,
        idempotency_key,
        method="POST",
        path=f"/essays/{essay_id}/snapshots",
        request_hash=payload_hash(payload.model_dump_json()),
        operation=operation,
    )


@router.get("/essays/{essay_id}/versions", response_model=VersionListResponse)
def list_versions(
    essay_id: uuid.UUID,
    limit: int = Query(default=service.DEFAULT_LIST_LIMIT, ge=1, le=service.MAX_LIST_LIMIT),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionListResponse:
    items, next_cursor, applied_limit = service.list_versions(
        db, user, essay_id, limit=limit, cursor=cursor
    )
    return VersionListResponse.model_validate(
        {
            "data": {"items": items, "next_cursor": next_cursor, "limit": applied_limit},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/essays/{essay_id}/versions/{version_id}", response_model=VersionResponse)
def get_version(
    essay_id: uuid.UUID,
    version_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionResponse:
    version = service.get_version(db, user, essay_id, version_id)
    return VersionResponse.model_validate(
        {"data": version, "meta": {"request_id": new_request_id()}}
    )


@router.post("/essays/{essay_id}/restore", response_model=RestoreResponse)
def restore_version(
    essay_id: uuid.UUID,
    payload: RestoreRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RestoreResponse:
    document, version = service.restore_version(db, user, essay_id, payload)
    return RestoreResponse.model_validate(
        {
            "data": {
                "essay_id": essay_id,
                "server_revision": document.server_revision,
                "restored_version_id": version.id,
                "word_count": document.word_count,
                "content_hash": document.content_hash,
                "saved_at": document.last_saved_at,
            },
            "meta": {"request_id": new_request_id()},
        }
    )
