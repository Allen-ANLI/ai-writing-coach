"""Workflow routes (thin): create, status, resume, cancel, events."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.users.models import User
from app.modules.workflows import service
from app.modules.workflows.schemas import (
    CreateWorkflowRequest,
    ResumeWorkflowRequest,
    WorkflowEventListResponse,
    WorkflowQueuedResponse,
    WorkflowResponse,
)
from app.schemas.common import new_request_id

router = APIRouter()


@router.post("/workflows", status_code=202, response_model=WorkflowQueuedResponse)
def create_workflow(
    payload: CreateWorkflowRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowQueuedResponse:
    workflow = service.create_workflow(db, user, payload)
    background_tasks.add_task(service.run_workflow, request.app.state.session_factory, workflow.id)
    return WorkflowQueuedResponse.model_validate(
        {
            "data": {"workflow_id": workflow.id, "status": workflow.status},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowResponse:
    workflow = service.get_workflow(db, user, workflow_id)
    return WorkflowResponse.model_validate(
        {"data": workflow, "meta": {"request_id": new_request_id()}}
    )


@router.post("/workflows/{workflow_id}/resume", status_code=202, response_model=WorkflowResponse)
def resume_workflow(
    workflow_id: uuid.UUID,
    payload: ResumeWorkflowRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowResponse:
    workflow, needs_rerun = service.resume_workflow(db, user, workflow_id, payload)
    if needs_rerun:
        background_tasks.add_task(
            service.run_workflow, request.app.state.session_factory, workflow.id
        )
    return WorkflowResponse.model_validate(
        {"data": workflow, "meta": {"request_id": new_request_id()}}
    )


@router.post("/workflows/{workflow_id}/cancel", response_model=WorkflowResponse)
def cancel_workflow(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowResponse:
    workflow = service.cancel_workflow(db, user, workflow_id)
    return WorkflowResponse.model_validate(
        {"data": workflow, "meta": {"request_id": new_request_id()}}
    )


@router.get("/workflows/{workflow_id}/events", response_model=WorkflowEventListResponse)
def list_events(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowEventListResponse:
    items = service.list_events(db, user, workflow_id)
    return WorkflowEventListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )
