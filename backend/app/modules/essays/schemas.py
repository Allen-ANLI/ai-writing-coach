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


# --- Slice 2B: Working Document, snapshots, versions, restore ---
# Shapes follow API Spec §4 and the contract's WorkingDocumentUpdate /
# WorkingDocumentSaved / SnapshotCreate schemas; response bodies the contract
# leaves open follow the §2 envelope + ERD field set.


class WorkingDocumentData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    essay_id: uuid.UUID
    content_json: dict
    plain_text: str
    word_count: int
    server_revision: int
    content_hash: str
    last_saved_at: datetime
    updated_at: datetime


class WorkingDocumentResponse(BaseModel):
    data: WorkingDocumentData
    meta: RequestMeta | None = None


class SaveWorkingDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    content_json: dict
    plain_text: str | None = None
    word_count: int | None = Field(default=None, ge=0)


class WorkingDocumentSavedData(BaseModel):
    essay_id: uuid.UUID
    server_revision: int
    client_revision: int
    saved: bool
    saved_at: datetime


class WorkingDocumentSavedResponse(BaseModel):
    data: WorkingDocumentSavedData
    meta: RequestMeta | None = None


SnapshotVersionType = Literal["checkpoint", "assisted", "final"]


class CreateSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_revision: int = Field(ge=1)
    # 'original' is created only at essay creation and 'ai_rewrite' only by
    # rewrite acceptance; neither may be created through this endpoint.
    version_type: SnapshotVersionType
    label: str | None = Field(default=None, max_length=255)


class VersionData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    essay_id: uuid.UUID
    version_no: int
    version_type: str
    label: str | None
    word_count: int
    source_revision: int
    parent_version_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime


class VersionDetailData(VersionData):
    content_json: dict
    plain_text: str
    content_hash: str


class VersionResponse(BaseModel):
    data: VersionDetailData
    meta: RequestMeta | None = None


class VersionListData(BaseModel):
    items: list[VersionData]
    next_cursor: str | None
    limit: int


class VersionListResponse(BaseModel):
    data: VersionListData
    meta: RequestMeta | None = None


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: uuid.UUID
    base_revision: int = Field(ge=1)


class RestoreData(BaseModel):
    essay_id: uuid.UUID
    server_revision: int
    restored_version_id: uuid.UUID
    word_count: int
    content_hash: str
    saved_at: datetime


class RestoreResponse(BaseModel):
    data: RestoreData
    meta: RequestMeta | None = None
