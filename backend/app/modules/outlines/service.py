"""Outline business logic: generation queueing, editing, confirmation, nodes.

The outline never writes into the essay body; ghost-text insertion is an
explicit user action in the editor (PRD FR-10.4).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing import service as billing_service
from app.modules.essays.service import get_essay
from app.modules.outlines.models import OutlineNode, WritingOutline
from app.modules.outlines.schemas import (
    CreateNodeRequest,
    GenerateOutlineRequest,
    PatchNodeRequest,
    PatchOutlineRequest,
)
from app.modules.users.models import User


def queue_generation(
    db: Session, user: User, essay_id: uuid.UUID, payload: GenerateOutlineRequest
) -> WritingOutline:
    essay = get_essay(db, user, essay_id)
    billing_service.guard_ai_call(db, user.id)
    next_no = (
        db.execute(
            select(func.coalesce(func.max(WritingOutline.version_no), 0)).where(
                WritingOutline.essay_id == essay.id
            )
        ).scalar_one()
        + 1
    )
    outline = WritingOutline(
        essay_id=essay.id,
        user_id=user.id,
        version_no=next_no,
        status="generating",
        thesis_statement=payload.viewpoint,
        source_context={
            "viewpoint": payload.viewpoint,
            "instructions": payload.instructions,
            "question_prompt": essay.question_prompt,
        },
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(outline)
    db.commit()
    db.refresh(outline)
    return outline


def list_outlines(db: Session, user: User, essay_id: uuid.UUID) -> list[WritingOutline]:
    get_essay(db, user, essay_id)
    rows = db.execute(
        select(WritingOutline)
        .where(WritingOutline.essay_id == essay_id, WritingOutline.user_id == user.id)
        .order_by(WritingOutline.version_no.desc())
    ).scalars()
    return list(rows)


def get_outline(db: Session, user: User, outline_id: uuid.UUID) -> WritingOutline:
    outline = db.execute(
        select(WritingOutline).where(
            WritingOutline.id == outline_id, WritingOutline.user_id == user.id
        )
    ).scalar_one_or_none()
    if outline is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Outline not found.")
    return outline


def _require_draft(outline: WritingOutline) -> None:
    if outline.status != "draft":
        raise ApiError(409, "VALIDATION_ERROR", "Only draft outlines can be edited.")


def patch_outline(
    db: Session, user: User, outline_id: uuid.UUID, payload: PatchOutlineRequest
) -> WritingOutline:
    outline = get_outline(db, user, outline_id)
    _require_draft(outline)
    if payload.thesis_statement is not None:
        outline.thesis_statement = payload.thesis_statement
    outline.updated_at = utcnow()
    db.commit()
    db.refresh(outline)
    return outline


def confirm_outline(db: Session, user: User, outline_id: uuid.UUID) -> WritingOutline:
    outline = get_outline(db, user, outline_id)
    if outline.status != "draft":
        raise ApiError(409, "VALIDATION_ERROR", "Only draft outlines can be confirmed.")
    if not outline.nodes:
        raise ApiError(409, "VALIDATION_ERROR", "Cannot confirm an empty outline.")
    outline.status = "confirmed"
    outline.confirmed_at = utcnow()
    outline.updated_at = utcnow()
    db.commit()
    db.refresh(outline)
    return outline


def create_node(
    db: Session, user: User, outline_id: uuid.UUID, payload: CreateNodeRequest
) -> OutlineNode:
    outline = get_outline(db, user, outline_id)
    _require_draft(outline)
    if payload.parent_id is not None:
        parent = db.get(OutlineNode, payload.parent_id)
        if parent is None or parent.outline_id != outline.id:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Parent node not found in this outline.")
    node = OutlineNode(
        outline_id=outline.id,
        parent_id=payload.parent_id,
        node_type=payload.node_type,
        title=payload.title,
        content=payload.content,
        sort_order=payload.sort_order,
    )
    db.add(node)
    outline.updated_at = utcnow()
    db.commit()
    db.refresh(node)
    return node


def _get_node(db: Session, outline: WritingOutline, node_id: uuid.UUID) -> OutlineNode:
    node = db.get(OutlineNode, node_id)
    if node is None or node.outline_id != outline.id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Node not found in this outline.")
    return node


def patch_node(
    db: Session, user: User, outline_id: uuid.UUID, node_id: uuid.UUID, payload: PatchNodeRequest
) -> OutlineNode:
    outline = get_outline(db, user, outline_id)
    _require_draft(outline)
    node = _get_node(db, outline, node_id)
    if payload.title is not None:
        node.title = payload.title
    if payload.content is not None:
        node.content = payload.content
    if payload.sort_order is not None:
        node.sort_order = payload.sort_order
    outline.updated_at = utcnow()
    db.commit()
    db.refresh(node)
    return node


def delete_node(db: Session, user: User, outline_id: uuid.UUID, node_id: uuid.UUID) -> None:
    outline = get_outline(db, user, outline_id)
    _require_draft(outline)
    node = _get_node(db, outline, node_id)
    db.delete(node)
    outline.updated_at = utcnow()
    db.commit()


def save_generated_outline(
    db: Session, outline: WritingOutline, thesis: str, sections: list[dict]
) -> None:
    """Persist LLM outline structure as a section->paragraph->idea tree."""
    outline.thesis_statement = thesis
    order = 0
    for section in sections:
        section_node = OutlineNode(
            outline_id=outline.id,
            node_type="section",
            title=section["title"][:255],
            sort_order=order,
        )
        db.add(section_node)
        db.flush()
        order += 1
        paragraph_order = 0
        for paragraph in section["paragraphs"]:
            paragraph_node = OutlineNode(
                outline_id=outline.id,
                parent_id=section_node.id,
                node_type="paragraph",
                title=paragraph["title"][:255],
                sort_order=paragraph_order,
            )
            db.add(paragraph_node)
            db.flush()
            paragraph_order += 1
            idea_order = 0
            for idea in paragraph["sentence_ideas"]:
                db.add(
                    OutlineNode(
                        outline_id=outline.id,
                        parent_id=paragraph_node.id,
                        node_type="sentence_idea",
                        title=idea[:255],
                        sort_order=idea_order,
                    )
                )
                idea_order += 1
    outline.status = "draft"
    outline.updated_at = utcnow()
