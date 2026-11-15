"""IELTS question bank routes (thin): search, detail, tags, random, favorites."""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.ielts import service
from app.modules.ielts.schemas import (
    FavoriteResponse,
    QuestionDetailResponse,
    QuestionListResponse,
    TagListResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


@router.get("/ielts/questions", response_model=QuestionListResponse)
def list_questions(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    question_type: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionListResponse:
    items, next_cursor, applied_limit = service.list_questions(
        db,
        user,
        limit=limit,
        cursor=cursor,
        task_type=task_type,
        topic=topic,
        question_type=question_type,
    )
    return QuestionListResponse.model_validate(
        {
            "data": {"items": items, "next_cursor": next_cursor, "limit": applied_limit},
            "meta": {"request_id": new_request_id()},
        }
    )


# Declared before /ielts/questions/{question_id} so "random" is not parsed as a UUID.
@router.get("/ielts/questions/random", response_model=QuestionDetailResponse)
def random_question(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionDetailResponse:
    question = service.random_question(db, user)
    return QuestionDetailResponse.model_validate(
        {"data": question, "meta": {"request_id": new_request_id()}}
    )


@router.get("/ielts/questions/{question_id}", response_model=QuestionDetailResponse)
def get_question(
    question_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionDetailResponse:
    question = service.get_question(db, user, question_id)
    return QuestionDetailResponse.model_validate(
        {"data": question, "meta": {"request_id": new_request_id()}}
    )


@router.get("/ielts/tags", response_model=TagListResponse)
def list_tags(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TagListResponse:
    items = service.list_tags(db)
    return TagListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.post(
    "/ielts/questions/{question_id}/favorite", status_code=201, response_model=FavoriteResponse
)
def favorite_question(
    question_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoriteResponse:
    service.favorite_question(db, user, question_id)
    return FavoriteResponse.model_validate(
        {
            "data": {"question_id": question_id, "favorited": True},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.delete("/ielts/questions/{question_id}/favorite", status_code=204)
def unfavorite_question(
    question_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.unfavorite_question(db, user, question_id)
    return Response(status_code=204)
