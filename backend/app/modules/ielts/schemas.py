"""IELTS question bank response schemas (API Spec §12, contract 1.2.0)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import RequestMeta


class TagRef(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class QuestionSummary(BaseModel):
    id: uuid.UUID
    task_type: str
    question_type: str | None
    prompt_text: str
    prompt_translation: str | None
    difficulty: str | None
    tags: list[TagRef]
    is_favorited: bool
    created_at: datetime


class QuestionDetail(QuestionSummary):
    source_type: str
    source_title: str | None
    license_status: str


class QuestionListData(BaseModel):
    items: list[QuestionSummary]
    next_cursor: str | None
    limit: int


class QuestionListResponse(BaseModel):
    data: QuestionListData
    meta: RequestMeta


class QuestionDetailResponse(BaseModel):
    data: QuestionDetail
    meta: RequestMeta


class TagCount(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    question_count: int


class TagListData(BaseModel):
    items: list[TagCount]


class TagListResponse(BaseModel):
    data: TagListData
    meta: RequestMeta


class FavoriteData(BaseModel):
    question_id: uuid.UUID
    favorited: bool


class FavoriteResponse(BaseModel):
    data: FavoriteData
    meta: RequestMeta
