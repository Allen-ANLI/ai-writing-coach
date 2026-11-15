"""Outline routes (thin): generate, list, detail, edit, confirm, node CRUD."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.outlines import chat, processing, service
from app.modules.outlines.schemas import (
    CreateNodeRequest,
    GenerateOutlineRequest,
    NodeResponse,
    OutlineListResponse,
    OutlineQueuedResponse,
    OutlineResponse,
    PatchNodeRequest,
    PatchOutlineRequest,
    PlannerChatRequest,
    PlannerChatResponse,
    PlannerMessagesResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


def _outline_response(outline) -> OutlineResponse:
    return OutlineResponse.model_validate(
        {"data": outline, "meta": {"request_id": new_request_id()}}
    )


@router.post(
    "/essays/{essay_id}/outlines/generate", status_code=202, response_model=OutlineQueuedResponse
)
def generate_outline(
    essay_id: uuid.UUID,
    payload: GenerateOutlineRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutlineQueuedResponse:
    outline = service.queue_generation(db, user, essay_id, payload)
    background_tasks.add_task(
        processing.process_outline_generation, request.app.state.session_factory, outline.id
    )
    return OutlineQueuedResponse.model_validate(
        {
            "data": {"outline_id": outline.id, "status": outline.status},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/essays/{essay_id}/outlines", response_model=OutlineListResponse)
def list_outlines(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutlineListResponse:
    items = service.list_outlines(db, user, essay_id)
    return OutlineListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.post("/essays/{essay_id}/planner/chat", response_model=PlannerChatResponse)
def planner_chat(
    essay_id: uuid.UUID,
    payload: PlannerChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlannerChatResponse:
    message, outline = chat.send_message(db, user, essay_id, payload.message.strip())
    return PlannerChatResponse.model_validate(
        {
            "data": {"message": message, "outline": outline},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/essays/{essay_id}/planner/messages", response_model=PlannerMessagesResponse)
def planner_messages(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlannerMessagesResponse:
    items = chat.list_messages(db, user, essay_id)
    return PlannerMessagesResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/outlines/{outline_id}", response_model=OutlineResponse)
def get_outline(
    outline_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutlineResponse:
    return _outline_response(service.get_outline(db, user, outline_id))


@router.patch("/outlines/{outline_id}", response_model=OutlineResponse)
def patch_outline(
    outline_id: uuid.UUID,
    payload: PatchOutlineRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutlineResponse:
    return _outline_response(service.patch_outline(db, user, outline_id, payload))


@router.post("/outlines/{outline_id}/confirm", response_model=OutlineResponse)
def confirm_outline(
    outline_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutlineResponse:
    return _outline_response(service.confirm_outline(db, user, outline_id))


@router.post("/outlines/{outline_id}/nodes", status_code=201, response_model=NodeResponse)
def create_node(
    outline_id: uuid.UUID,
    payload: CreateNodeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NodeResponse:
    node = service.create_node(db, user, outline_id, payload)
    return NodeResponse.model_validate({"data": node, "meta": {"request_id": new_request_id()}})


@router.patch("/outlines/{outline_id}/nodes/{node_id}", response_model=NodeResponse)
def patch_node(
    outline_id: uuid.UUID,
    node_id: uuid.UUID,
    payload: PatchNodeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NodeResponse:
    node = service.patch_node(db, user, outline_id, node_id, payload)
    return NodeResponse.model_validate({"data": node, "meta": {"request_id": new_request_id()}})


@router.delete("/outlines/{outline_id}/nodes/{node_id}", status_code=204)
def delete_node(
    outline_id: uuid.UUID,
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_node(db, user, outline_id, node_id)
    return Response(status_code=204)
