"""Outline API schemas (API Spec §14)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import RequestMeta


class GenerateOutlineRequest(BaseModel):
    viewpoint: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=2000)


class PatchOutlineRequest(BaseModel):
    thesis_statement: str | None = Field(default=None, max_length=1000)


class CreateNodeRequest(BaseModel):
    parent_id: uuid.UUID | None = None
    node_type: Literal["section", "paragraph", "sentence_idea"]
    title: str = Field(min_length=1, max_length=255)
    content: str | None = Field(default=None, max_length=5000)
    sort_order: int = Field(default=0, ge=0)


class PatchNodeRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, max_length=5000)
    sort_order: int | None = Field(default=None, ge=0)


class NodeData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    node_type: str
    title: str
    content: str | None
    sort_order: int


class OutlineData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    essay_id: uuid.UUID
    version_no: int
    status: str
    thesis_statement: str | None
    model_essay: str | None = None
    source_context: dict
    workflow_id: uuid.UUID | None
    created_at: datetime
    confirmed_at: datetime | None


class OutlineDetailData(OutlineData):
    nodes: list[NodeData]


class OutlineQueuedData(BaseModel):
    outline_id: uuid.UUID
    status: str


class OutlineQueuedResponse(BaseModel):
    data: OutlineQueuedData
    meta: RequestMeta


class OutlineListData(BaseModel):
    items: list[OutlineData]


class OutlineListResponse(BaseModel):
    data: OutlineListData
    meta: RequestMeta


class OutlineResponse(BaseModel):
    data: OutlineDetailData
    meta: RequestMeta


class NodeResponse(BaseModel):
    data: NodeData
    meta: RequestMeta


class PlannerChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class ChatMessageData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    outline_id: uuid.UUID | None
    created_at: datetime


class PlannerChatData(BaseModel):
    message: ChatMessageData
    outline: OutlineDetailData | None


class PlannerChatResponse(BaseModel):
    data: PlannerChatData
    meta: RequestMeta


class PlannerMessagesData(BaseModel):
    items: list[ChatMessageData]


class PlannerMessagesResponse(BaseModel):
    data: PlannerMessagesData
    meta: RequestMeta


class PlannerProgressRequest(BaseModel):
    sentence: str = Field(min_length=1, max_length=2000)
    idea_index: int = Field(ge=0)
    idea: str = Field(min_length=1, max_length=500)


class PlannerProgressData(BaseModel):
    fulfilled: bool
    reason: str | None
    degraded: bool


class PlannerProgressResponse(BaseModel):
    data: PlannerProgressData
    meta: RequestMeta
