"""Writing session request/response schemas (API Spec §5).

enabled_features is server-derived from mode; exam_config is validated for
mock_exam and must be absent otherwise. Response bodies follow the §2 envelope
(the contract leaves them open).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta

Mode = Literal["assisted", "independent"]
ActivityType = Literal["free_writing", "practice", "mock_exam"]


class ExamConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_type: str = Field(min_length=1, max_length=30)
    task_type: Literal["task1", "task2"]
    duration_minutes: int = Field(ge=1, le=180)
    word_limit: int | None = Field(default=None, ge=1, le=2000)


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Mode
    activity_type: ActivityType
    exam_config: ExamConfig | None = None


class PatchSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_config: ExamConfig | None = None
    status: Literal["cancelled"] | None = None


class SubmitSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_server_revision: int = Field(ge=1)


class EnabledFeatures(BaseModel):
    realtime_grammar: bool
    llm_assistance: bool
    chinese_to_english: bool
    expression_recommendations: bool
    ghost_text: bool
    paragraph_analysis: bool
    autosave: bool
    post_submission_evaluation: bool


class SessionData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    essay_id: uuid.UUID
    mode: str
    activity_type: str
    exam_config: dict | None
    started_at: datetime
    deadline_at: datetime | None
    submitted_at: datetime | None
    status: str
    created_at: datetime
    enabled_features: EnabledFeatures


class SessionResponse(BaseModel):
    data: SessionData
    meta: RequestMeta | None = None


class SessionListData(BaseModel):
    items: list[SessionData]


class SessionListResponse(BaseModel):
    data: SessionListData
    meta: RequestMeta | None = None


class SubmitData(BaseModel):
    session_id: uuid.UUID
    status: str
    submitted_at: datetime
    final_version_id: uuid.UUID
    server_revision: int
    shared_original: bool


class SubmitResponse(BaseModel):
    data: SubmitData
    meta: RequestMeta | None = None
