"""Essay routes (thin). Identity always comes from the auth context; essays
are scoped to the authenticated user and foreign resources return 404."""

import uuid

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.essays import service
from app.modules.essays.schemas import (
    CreateEssayRequest,
    EssayListResponse,
    EssayResponse,
    PatchEssayRequest,
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
