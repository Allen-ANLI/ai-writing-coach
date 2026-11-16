"""Conversational planner (ADR-024): chat with the agent to agree on and
revise the essay outline from the editor's left panel.

The LLM call happens OUTSIDE any DB transaction (AGENTS §4). Proposed and
revised outlines are stored as regular writing_outlines drafts via
service.save_generated_outline, so confirmation, ghost hints and ownership
rules are reused unchanged. Every call is quota-guarded and usage-logged.
"""

import hashlib
import math
import uuid
from collections import OrderedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.embeddings import embed_texts
from app.ai.prompts.registry import get_prompt
from app.ai.providers.base import LlmUsage
from app.ai.schemas import GhostProgressResult, PlannerChatResult
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing import service as billing_service
from app.modules.essays.service import get_essay
from app.modules.expressions import knowledge
from app.modules.outlines import service
from app.modules.outlines.models import OutlineChatMessage, WritingOutline
from app.modules.users.models import User

HISTORY_WINDOW = 20


def list_messages(db: Session, user: User, essay_id: uuid.UUID) -> list[OutlineChatMessage]:
    get_essay(db, user, essay_id)
    rows = db.execute(
        select(OutlineChatMessage)
        .where(OutlineChatMessage.essay_id == essay_id, OutlineChatMessage.user_id == user.id)
        .order_by(OutlineChatMessage.created_at.asc())
        .limit(200)
    ).scalars()
    return list(rows)


def _current_confirmed(db: Session, essay_id: uuid.UUID) -> WritingOutline | None:
    return db.execute(
        select(WritingOutline)
        .where(WritingOutline.essay_id == essay_id, WritingOutline.status == "confirmed")
        .order_by(WritingOutline.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def _create_draft(
    db: Session, user: User, essay_id: uuid.UUID, result: PlannerChatResult
) -> WritingOutline:
    next_no = (
        db.execute(
            select(func.coalesce(func.max(WritingOutline.version_no), 0)).where(
                WritingOutline.essay_id == essay_id
            )
        ).scalar_one()
        + 1
    )
    outline = WritingOutline(
        essay_id=essay_id,
        user_id=user.id,
        version_no=next_no,
        status="generating",
        source_context={"source": "planner_chat"},
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(outline)
    db.flush()
    service.save_generated_outline(
        db,
        outline,
        result.outline.thesis_statement,
        [section.model_dump() for section in result.outline.sections],
    )
    # ADR-032: English source essay + sentence-aligned Chinese translation
    # (drives ghost hints) + markdown outline for readable display.
    outline.model_essay = result.model_essay
    outline.model_essay_zh = result.model_essay_zh
    outline.outline_md = result.outline.outline_md
    return outline


def send_message(
    db: Session, user: User, essay_id: uuid.UUID, message: str
) -> tuple[OutlineChatMessage, WritingOutline | None]:
    essay = get_essay(db, user, essay_id)
    billing_service.guard_ai_call(db, user.id)

    history = list_messages(db, user, essay_id)[-HISTORY_WINDOW:]
    confirmed = _current_confirmed(db, essay_id)
    history_text = "\n".join(f"{m.role}: {m.content}" for m in history) or "(empty)"
    recalled = knowledge.semantic_candidates(db, user.id, message, limit=5)
    previously_learned = "; ".join(e.english_text for e in recalled) or "(none)"

    user_message = OutlineChatMessage(
        essay_id=essay.id, user_id=user.id, role="user", content=message, created_at=utcnow()
    )
    db.add(user_message)
    db.commit()  # no transaction held during the LLM call

    # ADR-034: outline_md uses ordered-list numbering (1. **短概括**…).
    prompt = get_prompt("planner_chat", "v7")
    user_prompt = prompt.user_template.format(
        question_prompt=essay.question_prompt or "(free writing)",
        current_outline=service.outline_json(confirmed),
        history=history_text,
        user_message=message,
        previously_learned=previously_learned,
    )
    try:
        result, usage = llm.call_llm(
            system=prompt.system, user=user_prompt, response_model=PlannerChatResult
        )
    except ApiError:
        llm.record_usage(
            db,
            user_id=user.id,
            feature="planner_chat",
            usage=_error_usage(),
            prompt_version=prompt.version,
            status="error",
        )
        db.commit()
        raise

    outline: WritingOutline | None = None
    if result.action in ("propose", "revise") and result.outline is not None:
        outline = _create_draft(db, user, essay.id, result)

    assistant_message = OutlineChatMessage(
        essay_id=essay.id,
        user_id=user.id,
        role="assistant",
        content=result.reply,
        outline_id=outline.id if outline is not None else None,
        created_at=utcnow(),
    )
    db.add(assistant_message)
    llm.record_usage(
        db,
        user_id=user.id,
        feature="planner_chat",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    db.refresh(assistant_message)
    if outline is not None:
        db.refresh(outline)
    return assistant_message, outline


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


# Ghost-guidance progress judgments (ADR-025). Deterministic per
# (user, idea, sentence); cached so re-renders never re-spend quota.
_PROGRESS_CACHE: OrderedDict[tuple, dict] = OrderedDict()
_PROGRESS_CACHE_MAX = 1024


def judge_progress(
    db: Session, user: User, essay_id: uuid.UUID, *, sentence: str, idea_index: int, idea: str
) -> dict:
    get_essay(db, user, essay_id)
    key = (
        user.id,
        idea_index,
        hashlib.sha256(f"{idea}\n{sentence}".encode()).hexdigest(),
    )
    cached = _PROGRESS_CACHE.get(key)
    if cached is not None:
        _PROGRESS_CACHE.move_to_end(key)
        return cached

    billing_service.guard_ai_call(db, user.id)
    db.commit()  # no transaction held during the LLM call
    prompt = get_prompt("ghost_progress", "v3")
    user_prompt = prompt.user_template.format(idea=idea, sentence=sentence)
    try:
        result, usage = llm.call_llm(
            system=prompt.system, user=user_prompt, response_model=GhostProgressResult
        )
    except ApiError:
        llm.record_usage(
            db,
            user_id=user.id,
            feature="ghost_progress",
            usage=_error_usage(),
            prompt_version=prompt.version,
            status="error",
        )
        db.commit()
        # Degraded mode: never block the writer when the provider is down.
        return {"fulfilled": True, "reason": None, "degraded": True}

    llm.record_usage(
        db,
        user_id=user.id,
        feature="ghost_progress",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    data = {"fulfilled": result.fulfilled, "reason": result.reason, "degraded": False}
    _PROGRESS_CACHE[key] = data
    _PROGRESS_CACHE.move_to_end(key)
    while len(_PROGRESS_CACHE) > _PROGRESS_CACHE_MAX:
        _PROGRESS_CACHE.popitem(last=False)
    return data


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def match_position(
    db: Session, user: User, essay_id: uuid.UUID, *, sentences: list[str], hints: list[str]
) -> dict:
    """ADR-033: locate the writer by position + embedding content match.

    Returns the number of LEADING user sentences that match the corresponding
    model sentence (cosine >= threshold). Position-based so deleting sentences
    retreats the index; the embedding gate only advances past a sentence whose
    gist matches. The mock embedding provider carries no semantics, so it
    degrades to pure position (matched = sentence count); a real embedding
    endpoint enables semantic gating. Embedding failure also degrades to
    position so the writer is never blocked."""
    get_essay(db, user, essay_id)
    n = min(len(sentences), len(hints))
    if n == 0:
        return {"matched": 0, "degraded": False}
    settings = get_settings()
    if settings.embedding_provider == "mock":
        return {"matched": n, "degraded": True}
    db.commit()  # no transaction held during the embedding call
    try:
        result = embed_texts(sentences[:n] + hints[:n])
    except ApiError:
        return {"matched": n, "degraded": True}
    threshold = settings.ghost_match_threshold
    matched = n
    for i in range(n):
        if _cosine(result.vectors[i], result.vectors[n + i]) < threshold:
            matched = i
            break
    return {"matched": matched, "degraded": False}
