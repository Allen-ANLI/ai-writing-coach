"""Outline business logic: generation queueing, editing, confirmation, nodes.

The outline never writes into the essay body; ghost-text insertion is an
explicit user action in the editor (PRD FR-10.4).

ADR-030: the model essay is the source of truth for ghost guidance. The
planner derives the outline FROM the essay; manual outline edits expire the
essay so confirmation regenerates a matching one. Every confirmed outline
therefore carries a consistent model essay.
"""

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.prompts.registry import get_prompt
from app.ai.providers.base import LlmUsage
from app.ai.schemas import ModelEssayResult
from app.core.config import get_settings
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


def outline_json(outline: WritingOutline | None) -> str:
    """Serialize an outline's section->paragraph->idea tree for prompts."""
    if outline is None:
        return "(none)"
    sections = []
    for section in sorted(
        (n for n in outline.nodes if n.parent_id is None), key=lambda n: n.sort_order
    ):
        paragraphs = []
        for paragraph in sorted(
            (n for n in outline.nodes if n.parent_id == section.id), key=lambda n: n.sort_order
        ):
            ideas = [
                n.title
                for n in sorted(
                    (n for n in outline.nodes if n.parent_id == paragraph.id),
                    key=lambda n: n.sort_order,
                )
            ]
            paragraphs.append({"title": paragraph.title, "sentence_ideas": ideas})
        sections.append({"title": section.title, "paragraphs": paragraphs})
    return json.dumps(
        {"thesis_statement": outline.thesis_statement, "sections": sections}, ensure_ascii=False
    )


def _error_usage() -> LlmUsage:
    settings = get_settings()
    return LlmUsage(
        provider=settings.llm_provider,
        model_name=settings.llm_model,
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
        estimated_cost=0.0,
    )


def ensure_model_essay(db: Session, user: User, outline_id: uuid.UUID) -> WritingOutline:
    """ADR-030: guarantee a model essay consistent with the outline. Generates
    one from the outline when missing (LLM outside any DB transaction); a
    no-op when the essay already exists. Raises ApiError on provider failure
    so callers can degrade gracefully (the outline stays usable)."""
    outline = get_outline(db, user, outline_id)
    if outline.model_essay and outline.model_essay.strip():
        return outline
    essay = get_essay(db, user, outline.essay_id)
    question_prompt = essay.question_prompt or "(free writing)"
    thesis = outline.thesis_statement or ""
    structure = outline_json(outline)
    billing_service.guard_ai_call(db, user.id)
    db.commit()  # no transaction held during the LLM call

    prompt = get_prompt("model_essay_generate", "v1")
    user_prompt = prompt.user_template.format(
        question_prompt=question_prompt, thesis=thesis, outline=structure
    )
    try:
        result, usage = llm.call_llm(
            system=prompt.system, user=user_prompt, response_model=ModelEssayResult
        )
    except ApiError:
        llm.record_usage(
            db,
            user_id=user.id,
            feature="model_essay_generate",
            usage=_error_usage(),
            prompt_version=prompt.version,
            status="error",
        )
        db.commit()
        raise

    outline = get_outline(db, user, outline_id)
    outline.model_essay = result.model_essay
    outline.updated_at = utcnow()
    llm.record_usage(
        db,
        user_id=user.id,
        feature="model_essay_generate",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    db.refresh(outline)
    return outline


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
    # ADR-030: editing the outline expires the model essay; confirmation
    # regenerates a matching one so guidance stays consistent.
    outline.model_essay = None
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
    # One current plan per essay: earlier confirmed versions become archived
    # (ADR-024 — the chat planner can revise the structure mid-writing).
    previous = db.execute(
        select(WritingOutline).where(
            WritingOutline.essay_id == outline.essay_id,
            WritingOutline.status == "confirmed",
            WritingOutline.id != outline.id,
        )
    ).scalars()
    for older in previous:
        older.status = "archived"
        older.updated_at = utcnow()
    outline.status = "confirmed"
    outline.confirmed_at = utcnow()
    outline.updated_at = utcnow()
    db.commit()
    db.refresh(outline)
    # ADR-030: a confirmed outline must carry a model essay for ghost guidance.
    # Generate one from the outline when missing (e.g. manual edits expired it,
    # workflow/legacy outlines). Failure does not block confirmation — the
    # panel offers a retry button.
    if not (outline.model_essay and outline.model_essay.strip()):
        try:
            outline = ensure_model_essay(db, user, outline_id)
        except ApiError:
            pass
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
    outline.model_essay = None  # ADR-030: outline changed, essay expires
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
    outline.model_essay = None  # ADR-030: outline changed, essay expires
    outline.updated_at = utcnow()
    db.commit()
    db.refresh(node)
    return node


def delete_node(db: Session, user: User, outline_id: uuid.UUID, node_id: uuid.UUID) -> None:
    outline = get_outline(db, user, outline_id)
    _require_draft(outline)
    node = _get_node(db, outline, node_id)
    db.delete(node)
    outline.model_essay = None  # ADR-030: outline changed, essay expires
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
