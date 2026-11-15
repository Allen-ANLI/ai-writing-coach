"""Workflow API schemas (API Spec §15). Business status only — no graph state."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta

WorkflowType = Literal["writing_planner", "learning_extractor", "personalized_study_planner"]
ResumeAction = Literal["confirm", "reject", "revise", "continue"]


class CreateWorkflowRequest(BaseModel):
    workflow_type: WorkflowType
    essay_id: uuid.UUID | None = None
    input: dict = Field(default_factory=dict)


class ResumeWorkflowRequest(BaseModel):
    action: ResumeAction
    input: dict = Field(default_factory=dict)


class WorkflowData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_type: str
    essay_id: uuid.UUID | None
    status: str
    current_step: str | None
    result_json: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowQueuedData(BaseModel):
    workflow_id: uuid.UUID
    status: str


class WorkflowQueuedResponse(BaseModel):
    data: WorkflowQueuedData
    meta: RequestMeta


class WorkflowResponse(BaseModel):
    data: WorkflowData
    meta: RequestMeta


class WorkflowEventData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    step: str
    event_type: str
    payload_json: dict
    created_at: datetime


class WorkflowEventListData(BaseModel):
    items: list[WorkflowEventData]


class WorkflowEventListResponse(BaseModel):
    data: WorkflowEventListData
    meta: RequestMeta
