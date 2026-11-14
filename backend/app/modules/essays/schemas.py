"""Essay request/response schemas.

The OpenAPI contract leaves essay response bodies open (descriptions only);
shapes here follow API Specification §2 (envelope, cursor pagination) and the
ERD field set. PATCH accepts title only in this slice (metadata editing beyond
title belongs to later slices).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta

WritingType = Literal["free_writing", "ielts_task1", "ielts_task2", "other"]


class CreateEssayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    writing_type: WritingType
    question_id: uuid.UUID | None = None


class PatchEssayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)


class WorkingDocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_revision: int
    word_count: int
    last_saved_at: datetime


class EssayData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    writing_type: str
    status: str
    question_id: uuid.UUID | None
    original_version_id: uuid.UUID | None
    final_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class EssayDetailData(EssayData):
    working_document: WorkingDocumentSummary


class EssayResponse(BaseModel):
    data: EssayDetailData
    meta: RequestMeta | None = None


class EssayListData(BaseModel):
    items: list[EssayData]
    next_cursor: str | None
    limit: int


class EssayListResponse(BaseModel):
    data: EssayListData
    meta: RequestMeta | None = None
