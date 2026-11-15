"""Evaluation/rewrite API schemas (API Spec §13, contract 1.2.0)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import RequestMeta


class CreateEvaluationRequest(BaseModel):
    version_id: uuid.UUID
    evaluation_type: Literal["ielts", "general"]
    task_type: Literal["task1", "task2"] | None = None


class EvaluationData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    essay_id: uuid.UUID
    version_id: uuid.UUID
    evaluation_type: str
    task_type: str | None
    status: str
    overall_band: float | None
    criteria_scores: dict | None
    feedback_json: dict | None
    is_estimate: bool
    model_name: str | None
    prompt_version: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class EvaluationQueuedData(BaseModel):
    evaluation_id: uuid.UUID
    status: str


class EvaluationQueuedResponse(BaseModel):
    data: EvaluationQueuedData
    meta: RequestMeta


class EvaluationListData(BaseModel):
    items: list[EvaluationData]


class EvaluationListResponse(BaseModel):
    data: EvaluationListData
    meta: RequestMeta


class EvaluationResponse(BaseModel):
    data: EvaluationData
    meta: RequestMeta


class CreateRewriteRequest(BaseModel):
    modification_level: Literal["level_1", "level_2", "level_3", "level_4"]


class RewriteData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evaluation_id: uuid.UUID
    source_version_id: uuid.UUID
    result_version_id: uuid.UUID | None
    modification_level: str
    status: str
    result_plain_text: str | None
    change_summary: str | None
    model_name: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class RewriteQueuedData(BaseModel):
    rewrite_id: uuid.UUID
    status: str


class RewriteQueuedResponse(BaseModel):
    data: RewriteQueuedData
    meta: RequestMeta


class RewriteResponse(BaseModel):
    data: RewriteData
    meta: RequestMeta


class AcceptRewriteRequest(BaseModel):
    base_revision: int
    client_revision: int


class AcceptRewriteData(BaseModel):
    rewrite_id: uuid.UUID
    result_version_id: uuid.UUID
    server_revision: int
    word_count: int


class AcceptRewriteResponse(BaseModel):
    data: AcceptRewriteData
    meta: RequestMeta
