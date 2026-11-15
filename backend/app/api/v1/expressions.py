"""Expression routes (thin): knowledge base CRUD + polish/translation/accept."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.expressions import knowledge, service
from app.modules.expressions.schemas import (
    AcceptSuggestionRequest,
    AcceptSuggestionResponse,
    CreateExpressionRequest,
    ExpressionListResponse,
    ExpressionResponse,
    PatchExpressionRequest,
    PolishRequest,
    SuggestionResponse,
    TranslationRequest,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


def _expression_response(expression) -> ExpressionResponse:
    return ExpressionResponse.model_validate(
        {"data": expression, "meta": {"request_id": new_request_id()}}
    )


def _suggestion_response(suggestion) -> SuggestionResponse:
    data = {
        "id": suggestion.id,
        "essay_id": suggestion.essay_id,
        "kind": suggestion.kind,
        "selected_text": suggestion.selected_text,
        "server_revision": suggestion.server_revision,
        "status": suggestion.status,
        "created_at": suggestion.created_at,
        "items": [
            {
                "id": item.id,
                "english_text": item.english_text,
                "chinese_meaning": item.chinese_meaning,
                "usage_note": item.usage_note,
                "register": item.register,
                "source": item.source,
                "expression_id": item.expression_id,
                "previously_learned": item.source == "previously_learned",
                "status": item.status,
            }
            for item in suggestion.items
        ],
    }
    return SuggestionResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


@router.post("/expressions", status_code=201, response_model=ExpressionResponse)
def create_expression(
    payload: CreateExpressionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpressionResponse:
    return _expression_response(service.create_expression(db, user, payload))


@router.get("/expressions", response_model=ExpressionListResponse)
def list_expressions(
    limit: int = Query(default=service.DEFAULT_LIST_LIMIT, ge=1, le=service.MAX_LIST_LIMIT),
    cursor: str | None = Query(default=None),
    status: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    query: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpressionListResponse:
    items, next_cursor, applied_limit = service.list_expressions(
        db, user, limit=limit, cursor=cursor, status=status, topic=topic, query=query
    )
    return ExpressionListResponse.model_validate(
        {
            "data": {"items": items, "next_cursor": next_cursor, "limit": applied_limit},
            "meta": {"request_id": new_request_id()},
        }
    )


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=500)
    mode: Literal["keyword", "semantic", "hybrid"] = "keyword"
    status: str | None = None
    topic: str | None = None
    limit: int = Field(default=service.DEFAULT_LIST_LIMIT, ge=1, le=service.MAX_LIST_LIMIT)
    cursor: str | None = None


@router.post("/expressions/search", response_model=ExpressionListResponse)
def search_expressions(
    payload: SearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpressionListResponse:
    if payload.mode in ("semantic", "hybrid") and payload.query:
        semantic_items = knowledge.semantic_candidates(
            db, user.id, payload.query, limit=payload.limit
        )
        if payload.mode == "semantic":
            return ExpressionListResponse.model_validate(
                {
                    "data": {"items": semantic_items, "next_cursor": None, "limit": payload.limit},
                    "meta": {"request_id": new_request_id()},
                }
            )
        keyword_items, _, _ = service.list_expressions(
            db,
            user,
            limit=payload.limit,
            cursor=None,
            status=payload.status,
            topic=payload.topic,
            query=payload.query,
        )
        seen = {item.id for item in semantic_items}
        merged = list(semantic_items) + [i for i in keyword_items if i.id not in seen]
        return ExpressionListResponse.model_validate(
            {
                "data": {
                    "items": merged[: payload.limit],
                    "next_cursor": None,
                    "limit": payload.limit,
                },
                "meta": {"request_id": new_request_id()},
            }
        )
    items, next_cursor, applied_limit = service.list_expressions(
        db,
        user,
        limit=payload.limit,
        cursor=payload.cursor,
        status=payload.status,
        topic=payload.topic,
        query=payload.query,
    )
    return ExpressionListResponse.model_validate(
        {
            "data": {"items": items, "next_cursor": next_cursor, "limit": applied_limit},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/expressions/{expression_id}", response_model=ExpressionResponse)
def get_expression(
    expression_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpressionResponse:
    return _expression_response(service.get_expression(db, user, expression_id))


@router.patch("/expressions/{expression_id}", response_model=ExpressionResponse)
def patch_expression(
    expression_id: uuid.UUID,
    payload: PatchExpressionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpressionResponse:
    return _expression_response(service.update_expression(db, user, expression_id, payload))


@router.delete("/expressions/{expression_id}", status_code=204)
def delete_expression(
    expression_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_expression(db, user, expression_id)
    return Response(status_code=204)


@router.post("/expressions/{expression_id}/archive", response_model=ExpressionResponse)
def archive_expression(
    expression_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpressionResponse:
    return _expression_response(service.archive_expression(db, user, expression_id))


@router.post("/essays/{essay_id}/expression-suggestions", response_model=SuggestionResponse)
def polish_expression(
    essay_id: uuid.UUID,
    payload: PolishRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuggestionResponse:
    return _suggestion_response(service.polish_expression(db, user, essay_id, payload))


@router.post("/essays/{essay_id}/translations", response_model=SuggestionResponse)
def translate_chinese(
    essay_id: uuid.UUID,
    payload: TranslationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuggestionResponse:
    return _suggestion_response(service.translate_chinese(db, user, essay_id, payload))


@router.post(
    "/essays/{essay_id}/expression-suggestions/{suggestion_id}/accept",
    response_model=AcceptSuggestionResponse,
)
def accept_suggestion(
    essay_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    payload: AcceptSuggestionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcceptSuggestionResponse:
    data = service.accept_suggestion(db, user, essay_id, suggestion_id, payload.item_id, payload)
    return AcceptSuggestionResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: uuid.UUID
    extraction_scope: Literal["full", "assisted_changes"] = "full"


@router.post("/essays/{essay_id}/expressions/extract", status_code=202)
def extract_expressions(
    essay_id: uuid.UUID,
    payload: ExtractRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = knowledge.extract_expressions(
        db, user, essay_id, payload.version_id, payload.extraction_scope
    )
    return {"data": data, "meta": {"request_id": new_request_id()}}
