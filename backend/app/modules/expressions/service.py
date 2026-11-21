"""Expression business logic (API Spec §8–9, PRD FR-03/04/06).

- Knowledge base CRUD is owner-scoped with soft delete and dedup on create.
- Polish/translation enforce session mode flags backend-side, call the LLM
  outside DB transactions, and persist candidates server-side.
- Previously-learned candidates come from the user's OWN knowledge base and
  must pass LLM contextual-suitability judgment (never pushed on similarity
  alone). Semantic retrieval upgrades this in the RAG slice.
- Acceptance applies the client-submitted replacement document only after
  ownership/revision/range validation, atomically with suggestion state and
  an Edit Event (AGENTS §4).
"""

import base64
import binascii
import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.prompts.registry import get_prompt
from app.ai.providers.base import LlmUsage
from app.ai.schemas import (
    PolishResult,
    PolishSentenceResult,
    PolishVerifyResult,
    TranslationResult,
)
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing import service as billing_service
from app.modules.essays import repository as essay_repository
from app.modules.essays import tiptap
from app.modules.essays.models import EssayEditEvent
from app.modules.essays.service import get_essay
from app.modules.expressions import knowledge, repository
from app.modules.expressions.models import (
    ExpressionSource,
    ExpressionSuggestion,
    ExpressionSuggestionItem,
    UserExpression,
)
from app.modules.expressions.schemas import (
    AcceptSuggestionRequest,
    CreateExpressionRequest,
    PatchExpressionRequest,
    PolishRequest,
    PolishSentenceRequest,
    TranslationRequest,
)
from app.modules.grammar.models import WritingIssue
from app.modules.users.models import User
from app.modules.writing_sessions import repository as session_repository
from app.modules.writing_sessions.service import enabled_features

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100


def _encode_cursor(item: UserExpression) -> str:
    payload = {"t": item.created_at.isoformat(), "i": str(item.id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return datetime.fromisoformat(payload["t"]), uuid.UUID(payload["i"])
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise ApiError(422, "VALIDATION_ERROR", "Invalid pagination cursor.") from None


def create_expression(db: Session, user: User, payload: CreateExpressionRequest) -> UserExpression:
    existing = repository.find_duplicates(db, user.id, payload.english_text.strip())
    if existing is not None:
        raise ApiError(
            409, "RESOURCE_ALREADY_EXISTS", "This expression is already in your knowledge base."
        )
    if payload.essay_id is not None:
        get_essay(db, user, payload.essay_id)
    now = utcnow()
    expression = UserExpression(
        user_id=user.id,
        english_text=payload.english_text.strip(),
        chinese_meaning=payload.chinese_meaning,
        original_text=payload.original_text,
        learning_value_reason=payload.learning_value_reason,
        usage_context=payload.usage_context,
        topic=payload.topic,
        register=payload.register_value,
        grammar_pattern=payload.grammar_pattern,
        tags=payload.tags,
        status="collected",
        created_at=now,
        updated_at=now,
    )
    db.add(expression)
    db.flush()
    db.add(
        ExpressionSource(
            expression_id=expression.id,
            source_type=payload.source_type,
            essay_id=payload.essay_id,
            source_context=payload.source_context,
            created_at=now,
        )
    )
    knowledge.ensure_embedding(db, expression)
    db.commit()
    db.refresh(expression)
    return expression


def get_expression(db: Session, user: User, expression_id: uuid.UUID) -> UserExpression:
    expression = repository.get_for_user(db, expression_id, user.id)
    if expression is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Expression not found.")
    return expression


def list_expressions(
    db: Session,
    user: User,
    *,
    limit: int,
    cursor: str | None,
    status: str | None,
    topic: str | None,
    query: str | None,
) -> tuple[list[UserExpression], str | None, int]:
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be between 1 and 100.")
    decoded = _decode_cursor(cursor) if cursor else None
    rows = repository.list_for_user(
        db, user.id, limit=limit, cursor=decoded, status=status, topic=topic, query=query
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1]) if has_more and items else None
    return items, next_cursor, limit


def update_expression(
    db: Session, user: User, expression_id: uuid.UUID, payload: PatchExpressionRequest
) -> UserExpression:
    expression = get_expression(db, user, expression_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(expression, field, value)
    expression.updated_at = utcnow()
    knowledge.ensure_embedding(db, expression)
    db.commit()
    db.refresh(expression)
    return expression


def delete_expression(db: Session, user: User, expression_id: uuid.UUID) -> None:
    expression = get_expression(db, user, expression_id)
    expression.deleted_at = utcnow()
    db.commit()


def archive_expression(db: Session, user: User, expression_id: uuid.UUID) -> UserExpression:
    expression = get_expression(db, user, expression_id)
    expression.status = "archived"
    expression.updated_at = utcnow()
    db.commit()
    db.refresh(expression)
    return expression


def _assisted_session(db: Session, user: User, essay_id: uuid.UUID, session_id: uuid.UUID):
    session = session_repository.get_for_user(db, session_id, user.id)
    if session is None or session.essay_id != essay_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Writing session not found.")
    if session.status != "active":
        raise ApiError(400, "VALIDATION_ERROR", "The writing session is not active.")
    return session


def _previously_learned_context(db: Session, user: User, text: str) -> str:
    # Semantic recall first (user-scoped pgvector); keyword fallback when
    # embeddings are unavailable. Suitability is still judged by the LLM.
    candidates = knowledge.semantic_candidates(db, user.id, text)
    if not candidates:
        candidates = repository.keyword_candidates(db, user.id, text)
    if not candidates:
        return "none"
    return "; ".join(
        f"{c.english_text} ({c.chinese_meaning or 'no meaning recorded'})" for c in candidates
    )


def polish_expression(
    db: Session, user: User, essay_id: uuid.UUID, payload: PolishRequest
) -> ExpressionSuggestion:
    get_essay(db, user, essay_id)
    session = _assisted_session(db, user, essay_id, payload.session_id)
    if not enabled_features(session.mode).expression_recommendations:
        raise ApiError(
            403,
            "RESOURCE_ACCESS_DENIED",
            "Expression assistance is disabled in independent writing mode.",
        )
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.server_revision:
        raise ApiError(
            409, "STALE_AI_RESULT", "The document changed; retry at the current revision."
        )
    learned = _previously_learned_context(db, user, payload.sentence)
    db.commit()  # no transaction held during the LLM call

    prompt = get_prompt("expression_polish", "v1")
    user_prompt = prompt.user_template.format(
        selected_text=payload.selected_text,
        sentence=payload.sentence,
        paragraph_context=payload.paragraph_context or payload.sentence,
        previously_learned=learned,
        max_suggestions=payload.max_suggestions,
    )
    billing_service.guard_ai_call(db, user.id)
    result, usage = llm.call_llm(
        system=prompt.system, user=user_prompt, response_model=PolishResult
    )

    now = utcnow()
    suggestion = ExpressionSuggestion(
        essay_id=essay_id,
        user_id=user.id,
        kind="polish",
        selected_text=payload.selected_text,
        sentence_context=payload.sentence,
        paragraph_context=payload.paragraph_context,
        server_revision=payload.server_revision,
        status="pending",
        created_at=now,
    )
    db.add(suggestion)
    db.flush()
    learned_pool = knowledge.semantic_candidates(db, user.id, payload.sentence)
    if not learned_pool:
        learned_pool = repository.keyword_candidates(db, user.id, payload.sentence)
    learned_texts = {c.english_text.lower() for c in learned_pool}
    for order, item in enumerate(result.suggestions[: payload.max_suggestions]):
        is_learned = item.text.strip().lower() in learned_texts
        expression_id = None
        if is_learned:
            match = repository.find_duplicates(db, user.id, item.text.strip())
            expression_id = match.id if match else None
        db.add(
            ExpressionSuggestionItem(
                suggestion_id=suggestion.id,
                english_text=item.text,
                chinese_meaning=item.meaning,
                usage_note=item.usage,
                register=item.formality,
                source="previously_learned" if expression_id else "llm",
                expression_id=expression_id,
                sort_order=order,
                created_at=now,
            )
        )
    llm.record_usage(
        db,
        user_id=user.id,
        feature="expression_polish",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    db.refresh(suggestion)
    return suggestion


def translate_chinese(
    db: Session, user: User, essay_id: uuid.UUID, payload: TranslationRequest
) -> ExpressionSuggestion:
    get_essay(db, user, essay_id)
    session = _assisted_session(db, user, essay_id, payload.session_id)
    if not enabled_features(session.mode).chinese_to_english:
        raise ApiError(
            403,
            "RESOURCE_ACCESS_DENIED",
            "Chinese-to-English assistance is disabled in independent writing mode.",
        )
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.server_revision:
        raise ApiError(
            409, "STALE_AI_RESULT", "The document changed; retry at the current revision."
        )
    learned = _previously_learned_context(db, user, payload.sentence_context)
    db.commit()  # no transaction held during the LLM call

    prompt = get_prompt("translation", "v2")
    user_prompt = prompt.user_template.format(
        chinese_text=payload.chinese_text,
        sentence_context=payload.sentence_context,
        paragraph_context=payload.paragraph_context or payload.sentence_context,
        previously_learned=learned,
        exclude="; ".join(payload.exclude) or "(none)",
    )
    billing_service.guard_ai_call(db, user.id)
    result, usage = llm.call_llm(
        system=prompt.system, user=user_prompt, response_model=TranslationResult
    )

    now = utcnow()
    suggestion = ExpressionSuggestion(
        essay_id=essay_id,
        user_id=user.id,
        kind="translation",
        selected_text=payload.chinese_text,
        sentence_context=payload.sentence_context,
        paragraph_context=payload.paragraph_context,
        server_revision=payload.server_revision,
        status="pending",
        created_at=now,
    )
    db.add(suggestion)
    db.flush()
    for order, candidate in enumerate(result.candidates):
        match = repository.find_duplicates(db, user.id, candidate.english_text.strip())
        db.add(
            ExpressionSuggestionItem(
                suggestion_id=suggestion.id,
                english_text=candidate.english_text,
                chinese_meaning=candidate.chinese_meaning,
                usage_note=candidate.usage_note,
                register=candidate.formality,
                source="previously_learned" if match else "llm",
                expression_id=match.id if match else None,
                sort_order=order,
                created_at=now,
            )
        )
    llm.record_usage(
        db,
        user_id=user.id,
        feature="translation",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    db.refresh(suggestion)
    return suggestion


def accept_suggestion(
    db: Session,
    user: User,
    essay_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: AcceptSuggestionRequest,
) -> dict:
    """Atomic acceptance (API Spec §8): validate ownership/revision/range,
    apply the submitted replacement document, update suggestion state, create
    an Edit Event — one transaction, second revision check before writing."""
    essay = get_essay(db, user, essay_id)
    suggestion = repository.get_suggestion_for_user(db, suggestion_id, user.id)
    if suggestion is None or suggestion.essay_id != essay_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Suggestion not found.")
    if suggestion.status != "pending":
        raise ApiError(409, "VALIDATION_ERROR", "This suggestion was already handled.")
    item = repository.get_item_for_suggestion(db, suggestion_id, item_id)
    if item is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Suggestion item not found.")

    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.base_revision:
        raise ApiError(
            409, "WORKING_DOCUMENT_CONFLICT", "The working document changed; reload and retry."
        )

    content_json = tiptap.validate_document(payload.content_json)
    new_text, word_count = tiptap.derive_text(content_json)
    tiptap.check_client_values(payload.plain_text, payload.word_count, new_text, word_count)

    # The replacement must actually contain the chosen expression text.
    if item.english_text.strip() not in new_text:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "The submitted document does not contain the chosen expression.",
        )

    now = utcnow()
    old_revision = document.server_revision
    before_text = document.plain_text
    document.content_json = content_json
    document.plain_text = new_text
    document.word_count = word_count
    document.server_revision += 1
    document.content_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
    document.last_saved_at = now
    document.updated_at = now
    essay.updated_at = now

    suggestion.status = "accepted"
    item.status = "accepted"
    for other in suggestion.items:
        if other.id != item.id and other.status == "pending":
            other.status = "dismissed"

    # ADR-028: the replacement edits the document, so grammar findings must
    # be reconciled against the changed range instead of carried over:
    # anchors intersecting it go stale, later anchors shift, survivors bump
    # their source revision (the region is re-checked by the client).
    rep_start = payload.modified_range.get("start", 0)
    rep_end = payload.modified_range.get("end", rep_start)
    delta = len(new_text) - len(before_text)
    grammar_others = db.execute(
        select(WritingIssue).where(
            WritingIssue.essay_id == essay_id,
            WritingIssue.status == "detected",
            WritingIssue.source_server_revision == old_revision,
        )
    ).scalars()
    for issue in grammar_others:
        if issue.start_offset < rep_end and issue.end_offset > rep_start:
            issue.status = "stale"
        else:
            if issue.start_offset >= rep_end:
                issue.start_offset += delta
                issue.end_offset += delta
            issue.source_server_revision = document.server_revision
        issue.updated_at = now

    db.add(
        EssayEditEvent(
            essay_id=essay_id,
            from_server_revision=old_revision,
            to_server_revision=document.server_revision,
            expression_suggestion_id=item.id,
            actor_type="ai_accept",
            event_type="accept_suggestion",
            before_text=before_text,
            after_text=new_text,
            event_metadata={"kind": suggestion.kind, "expression": item.english_text},
            created_at=now,
        )
    )
    db.commit()

    return {
        "suggestion_id": suggestion.id,
        "item_id": item.id,
        "server_revision": document.server_revision,
        "content_json": content_json,
        "plain_text": new_text,
        "word_count": word_count,
    }


def polish_sentence(
    db: Session, user: User, essay_id: uuid.UUID, payload: PolishSentenceRequest
) -> dict:
    """ADR-026 fragment-level polish: scan a completed sentence (or fetch more
    options for one fragment). Natural sentences yield zero fragments.
    Offsets are validated against the sentence and stored absolute.

    ADR-036: detection uses the narrowed v3 criterion, and every candidate is
    substitution-re-checked by the SAME judge before being offered or persisted
    (the judge re-checks its own flag and judges the option inserted back into
    the sentence). Verify failure fails closed."""
    get_essay(db, user, essay_id)
    session = _assisted_session(db, user, essay_id, payload.session_id)
    if not enabled_features(session.mode).expression_recommendations:
        raise ApiError(
            403,
            "RESOURCE_ACCESS_DENIED",
            "Expression assistance is disabled in independent writing mode.",
        )
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.server_revision:
        raise ApiError(
            409, "STALE_AI_RESULT", "The document changed; retry at the current revision."
        )
    sentence_start = payload.sentence_range.get("start", 0)
    learned = _previously_learned_context(db, user, payload.sentence)
    db.commit()  # no transaction held during the LLM call

    prompt = get_prompt("expression_polish", "v3")
    user_prompt = prompt.user_template.format(
        sentence=payload.sentence,
        paragraph_context=payload.paragraph_context or payload.sentence,
        previously_learned=learned,
        exclude="; ".join(payload.exclude) or "(none)",
        focus_fragment=payload.fragment_anchor or "",
    )
    billing_service.guard_ai_call(db, user.id)
    result, usage = llm.call_llm(
        system=prompt.system, user=user_prompt, response_model=PolishSentenceResult
    )

    now = utcnow()
    cps = len(payload.sentence)
    # Phase 1: validate model offsets and collect candidates (no persistence).
    candidates: list[dict] = []
    for fragment in result.fragments:
        start, end = fragment.start_offset, fragment.end_offset
        if not (0 <= start < end <= cps):
            continue
        anchor = payload.sentence[start:end]
        if anchor != fragment.anchor_text:
            found = payload.sentence.find(fragment.anchor_text)
            if found < 0:
                continue
            start, end = found, found + len(fragment.anchor_text)
            anchor = fragment.anchor_text
        if payload.fragment_anchor and anchor != payload.fragment_anchor:
            continue
        candidates.append(
            {
                "anchor": anchor,
                "start": start,
                "end": end,
                "note": fragment.note,
                "options": list(fragment.options),
                "option_indices": [],
            }
        )

    # Phase 2 (ADR-036): substitution re-check by the SAME judge before anything
    # is offered or persisted. The judge re-checks its own flag (reject false
    # positives) and judges each option substituted back into the sentence; only
    # original_unnatural=true AND option_unnatural=false candidates survive. A
    # verify failure fails closed — no unverified option is ever shown.
    if candidates:
        lines: list[str] = []
        n = 0
        for cand in candidates:
            for option in cand["options"]:
                n += 1
                cand["option_indices"].append(n)
                substituted = (
                    payload.sentence[: cand["start"]]
                    + option.text
                    + payload.sentence[cand["end"] :]
                )
                lines.append(f"[{n}] anchor: {cand['anchor']} | option: {option.text}")
                lines.append(f"    substituted: {substituted}")
        verify_prompt = get_prompt("polish_verify", "v1")
        verify_user = verify_prompt.user_template.format(
            sentence=payload.sentence, candidates="\n".join(lines)
        )
        try:
            billing_service.guard_ai_call(db, user.id)
            verify_result, verify_usage = llm.call_llm(
                system=verify_prompt.system,
                user=verify_user,
                response_model=PolishVerifyResult,
            )
        except ApiError:
            llm.record_usage(
                db,
                user_id=user.id,
                feature="polish_verify",
                usage=_verify_error_usage(),
                prompt_version=verify_prompt.version,
                status="error",
            )
            llm.record_usage(
                db,
                user_id=user.id,
                feature="expression_polish",
                usage=usage,
                prompt_version=prompt.version,
                status="success",
            )
            db.commit()
            return {"fragments": []}
        verdicts = {r.candidate_index: r for r in verify_result.results}
        for cand in candidates:
            kept = []
            for oi, option in enumerate(cand["options"]):
                verdict = verdicts.get(cand["option_indices"][oi])
                if (
                    verdict is not None
                    and verdict.original_unnatural
                    and not verdict.option_unnatural
                ):
                    kept.append(option)
            cand["options"] = kept
        candidates = [cand for cand in candidates if cand["options"]]
        llm.record_usage(
            db,
            user_id=user.id,
            feature="polish_verify",
            usage=verify_usage,
            prompt_version=verify_prompt.version,
            status="success",
        )

    # Phase 3: persist only the verified survivors.
    learned_pool = knowledge.semantic_candidates(db, user.id, payload.sentence)
    if not learned_pool:
        learned_pool = repository.keyword_candidates(db, user.id, payload.sentence)
    learned_texts = {c.english_text.lower() for c in learned_pool}

    fragments_out: list[dict] = []
    for cand in candidates:
        suggestion = ExpressionSuggestion(
            essay_id=essay_id,
            user_id=user.id,
            kind="polish",
            selected_text=cand["anchor"],
            sentence_context=payload.sentence,
            paragraph_context=payload.paragraph_context,
            server_revision=payload.server_revision,
            status="pending",
            created_at=now,
        )
        db.add(suggestion)
        db.flush()
        items_out: list[dict] = []
        for order, option in enumerate(cand["options"]):
            is_learned = option.text.strip().lower() in learned_texts
            expression_id = None
            if is_learned:
                match = repository.find_duplicates(db, user.id, option.text.strip())
                expression_id = match.id if match else None
            item = ExpressionSuggestionItem(
                suggestion_id=suggestion.id,
                english_text=option.text,
                chinese_meaning=option.meaning,
                usage_note=option.usage,
                register=option.formality,
                source="previously_learned" if expression_id else "llm",
                expression_id=expression_id,
                sort_order=order,
                start_offset=sentence_start + cand["start"],
                end_offset=sentence_start + cand["end"],
                created_at=now,
            )
            db.add(item)
            db.flush()
            items_out.append(
                {
                    "id": item.id,
                    "english_text": item.english_text,
                    "chinese_meaning": item.chinese_meaning,
                    "usage_note": item.usage_note,
                    "register": item.register,
                    "source": item.source,
                    "expression_id": item.expression_id,
                    "previously_learned": item.source == "previously_learned",
                    "start_offset": item.start_offset,
                    "end_offset": item.end_offset,
                    "status": item.status,
                }
            )
        fragments_out.append(
            {
                "suggestion_id": suggestion.id,
                "anchor_text": cand["anchor"],
                "start_offset": sentence_start + cand["start"],
                "end_offset": sentence_start + cand["end"],
                "note": cand["note"],
                "items": items_out,
            }
        )
    llm.record_usage(
        db,
        user_id=user.id,
        feature="expression_polish",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    return {"fragments": fragments_out}


def _verify_error_usage() -> LlmUsage:
    settings = get_settings()
    return LlmUsage(
        provider=settings.llm_provider,
        model_name=settings.llm_model,
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
        estimated_cost=0.0,
    )


def list_essay_suggestions(db: Session, user: User, essay_id: uuid.UUID) -> list[dict]:
    """ADR-026 records: polish/translation history for the essay review UI."""
    get_essay(db, user, essay_id)
    rows = db.execute(
        select(ExpressionSuggestion)
        .where(ExpressionSuggestion.essay_id == essay_id, ExpressionSuggestion.user_id == user.id)
        .order_by(ExpressionSuggestion.created_at.desc())
        .limit(200)
    ).scalars()
    out: list[dict] = []
    for suggestion in rows:
        out.append(
            {
                "id": suggestion.id,
                "kind": suggestion.kind,
                "selected_text": suggestion.selected_text,
                "sentence_context": suggestion.sentence_context,
                "status": suggestion.status,
                "created_at": suggestion.created_at,
                "items": [
                    {
                        "id": item.id,
                        "english_text": item.english_text,
                        "chinese_meaning": item.chinese_meaning,
                        "usage_note": item.usage_note,
                        "status": item.status,
                        "start_offset": item.start_offset,
                        "end_offset": item.end_offset,
                    }
                    for item in suggestion.items
                ],
            }
        )
    return out
