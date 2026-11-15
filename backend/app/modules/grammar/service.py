"""Grammar business logic (API Spec §6–7, SD §5).

Pipeline: rule-first (LanguageTool + custom deterministic rules) → classify →
rule-template short explanations for high-confidence hits → LLM deep check ONLY
for uncertain fragments (capped) → persist issues bound to source_server_revision.

Invariants enforced here:
- Independent mode never receives real-time assistance (backend check).
- Unrevealed suggested_text never appears in check/list/detail responses.
- LLM/LanguageTool network calls run with no open DB transaction; persistence
  happens in short transactions afterwards, re-checking base_revision.
- Validation accepts contextually valid alternatives, not one reference answer.
"""

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.prompts.registry import get_prompt
from app.ai.schemas import DeepCheckResult, TeachingContent, ValidationJudgement
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.infrastructure.language_tool import client as language_tool
from app.modules.essays import repository as essay_repository
from app.modules.essays import tiptap
from app.modules.essays.models import EssayEditEvent
from app.modules.essays.service import get_essay
from app.modules.grammar import rules
from app.modules.grammar.models import IssueSuggestion, IssueTeaching, WritingIssue
from app.modules.grammar.schemas import (
    GrammarCheckRequest,
    IssueValidationRequest,
    TeachingRequest,
)
from app.modules.learning import service as learning_service
from app.modules.users.models import User
from app.modules.writing_sessions import repository as session_repository
from app.modules.writing_sessions.service import enabled_features

_MAX_LLM_FRAGMENTS_PER_CHECK = 3
_MASKED_DISPLAY = "••••"


@dataclass
class _UsageEntry:
    feature: str
    prompt_version: str
    usage: llm.LlmUsage
    status: str


def _active_session(db: Session, user: User, essay_id: uuid.UUID, session_id: uuid.UUID):
    session = session_repository.get_for_user(db, session_id, user.id)
    if session is None or session.essay_id != essay_id:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Writing session not found.")
    if session.status != "active":
        raise ApiError(400, "VALIDATION_ERROR", "The writing session is not active.")
    return session


def _issue_stub_data(issue: WritingIssue) -> dict:
    return {
        "id": issue.id,
        "category": issue.category,
        "sub_category": issue.sub_category,
        "source": issue.source,
        "rule_id": issue.rule_id,
        "severity": issue.severity,
        "source_server_revision": issue.source_server_revision,
        "essay_version_id": issue.essay_version_id,
        "start_offset": issue.start_offset,
        "end_offset": issue.end_offset,
        "offset_unit": issue.offset_unit,
        "anchor_text": issue.anchor_text,
        "short_explanation": issue.short_explanation,
        "status": issue.status,
        "suggestions": [
            {"id": s.id, "display_text": _MASKED_DISPLAY, "answer_revealed": False}
            for s in issue.suggestions
        ],
    }


def _run_rule_engine(text: str) -> tuple[list[rules.DetectedIssue], bool]:
    """Returns (issues, language_tool_ok). Degrades to custom rules when LT down."""
    custom = rules.custom_rules(text)
    try:
        matches = language_tool.check_text(text)
    except ApiError:
        return custom, False
    lt_issues = [
        classified
        for match in matches
        if (classified := rules.classify_lt_match(match, text)) is not None
    ]
    return rules.merge_issues(lt_issues, custom), True


def _deep_check_uncertain(
    uncertain: list[rules.DetectedIssue],
    text: str,
    paragraph: str | None,
    user_id: uuid.UUID,
    usages: list[_UsageEntry],
) -> tuple[list[rules.DetectedIssue], bool]:
    """LLM confirmation for uncertain fragments only; capped per check."""
    confirmed: list[rules.DetectedIssue] = []
    all_ok = True
    prompt = get_prompt("grammar_deep_check", "v1")
    for detected in uncertain[:_MAX_LLM_FRAGMENTS_PER_CHECK]:
        user_prompt = prompt.user_template.format(
            sentence=text,
            paragraph=paragraph or text,
            fragment=detected.anchor_text,
            rule_message=detected.rule_message or detected.short_explanation,
        )
        try:
            result, usage = llm.call_llm(
                system=prompt.system, user=user_prompt, response_model=DeepCheckResult
            )
        except ApiError:
            all_ok = False
            continue
        usages.append(_UsageEntry("grammar_deep_check", prompt.version, usage, "success"))
        for item in result.issues:
            if not item.confirmed:
                continue
            confirmed.append(
                rules.DetectedIssue(
                    category=item.category,
                    sub_category=item.sub_category,
                    source="llm",
                    rule_id=f"llm:{item.category}",
                    severity=item.severity,
                    confidence=item.confidence,
                    start_offset=detected.start_offset,
                    end_offset=detected.end_offset,
                    anchor_text=detected.anchor_text,
                    short_explanation=item.short_explanation,
                    suggestions=item.suggestions,
                )
            )
    if len(uncertain) > _MAX_LLM_FRAGMENTS_PER_CHECK:
        all_ok = False
    return confirmed, all_ok


def grammar_check(
    db: Session, user: User, essay_id: uuid.UUID, payload: GrammarCheckRequest
) -> dict:
    get_essay(db, user, essay_id)
    session = _active_session(db, user, essay_id, payload.session_id)
    if not enabled_features(session.mode).realtime_grammar:
        raise ApiError(
            403,
            "RESOURCE_ACCESS_DENIED",
            "Real-time grammar assistance is disabled in independent writing mode.",
        )
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.server_revision:
        raise ApiError(409, "STALE_AI_RESULT", "The document changed; check the current revision.")
    full_text = document.plain_text
    start, end = payload.text_range.start, payload.text_range.end
    if end > len(full_text) or full_text[start:end] != payload.text:
        raise ApiError(
            422, "VALIDATION_ERROR", "text_range does not match the working document text."
        )
    paragraph = (payload.context or {}).get("paragraph_text")
    db.commit()  # close the read transaction before network calls

    usages: list[_UsageEntry] = []
    detected, lt_ok = _run_rule_engine(payload.text)
    deterministic = [d for d in detected if not d.needs_llm]
    uncertain = [d for d in detected if d.needs_llm]
    llm_confirmed, llm_ok = _deep_check_uncertain(
        uncertain, payload.text, paragraph, user.id, usages
    )
    final = rules.merge_issues(deterministic, llm_confirmed)
    check_status = "completed" if (lt_ok and llm_ok) else "partial"

    # Short persistence transaction; offsets are absolute in the document.
    now = utcnow()
    existing = list(
        db.execute(
            select(WritingIssue).where(
                WritingIssue.essay_id == essay_id,
                WritingIssue.source_server_revision == document.server_revision,
                WritingIssue.status == "detected",
            )
        ).scalars()
    )
    existing_by_key = {(i.rule_id, i.start_offset, i.end_offset): i for i in existing}
    new_keys = set()
    persisted: list[WritingIssue] = []
    for d in final:
        abs_start = start + d.start_offset
        abs_end = start + d.end_offset
        key = (d.rule_id, abs_start, abs_end)
        new_keys.add(key)
        issue = existing_by_key.get(key)
        if issue is None:
            issue = WritingIssue(
                essay_id=essay_id,
                user_id=user.id,
                source_server_revision=document.server_revision,
                category=d.category,
                sub_category=d.sub_category,
                source=d.source,
                rule_id=d.rule_id,
                severity=d.severity,
                confidence=d.confidence,
                start_offset=abs_start,
                end_offset=abs_end,
                offset_unit="unicode_codepoint",
                anchor_text=d.anchor_text,
                prefix_context=full_text[max(0, abs_start - 60) : abs_start],
                suffix_context=full_text[abs_end : abs_end + 60],
                short_explanation=d.short_explanation,
                status="detected",
                created_at=now,
                updated_at=now,
            )
            db.add(issue)
            db.flush()
            learning_service.record_weakness_occurrence(db, user.id, d.category, d.sub_category)
            for order, suggestion_text in enumerate(d.suggestions):
                db.add(
                    IssueSuggestion(
                        issue_id=issue.id,
                        suggested_text=suggestion_text,
                        is_recommended=order == 0,
                        sort_order=order,
                        source="llm" if d.source == "llm" else "rule_engine",
                        created_at=now,
                    )
                )
        persisted.append(issue)
    for issue in existing:
        if (issue.rule_id, issue.start_offset, issue.end_offset) not in new_keys:
            issue.status = "stale"
            issue.updated_at = now
    for entry in usages:
        llm.record_usage(
            db,
            user_id=user.id,
            feature=entry.feature,
            usage=entry.usage,
            prompt_version=entry.prompt_version,
            status=entry.status,
        )
    db.commit()
    for issue in persisted:
        db.refresh(issue)

    return {
        "server_revision": document.server_revision,
        "client_revision": payload.client_revision,
        "check_status": check_status,
        "issues": [_issue_stub_data(issue) for issue in persisted],
    }


def _get_issue(db: Session, user: User, essay_id: uuid.UUID, issue_id: uuid.UUID) -> WritingIssue:
    get_essay(db, user, essay_id)
    issue = db.execute(
        select(WritingIssue).where(
            WritingIssue.id == issue_id,
            WritingIssue.essay_id == essay_id,
            WritingIssue.user_id == user.id,
        )
    ).scalar_one_or_none()
    if issue is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Issue not found.")
    return issue


def list_issues(
    db: Session, user: User, essay_id: uuid.UUID, *, revision: int | None, status: str | None
) -> list[dict]:
    get_essay(db, user, essay_id)
    query = select(WritingIssue).where(WritingIssue.essay_id == essay_id)
    if revision is not None:
        query = query.where(WritingIssue.source_server_revision == revision)
    if status is not None:
        query = query.where(WritingIssue.status == status)
    query = query.order_by(WritingIssue.start_offset, WritingIssue.created_at)
    return [_issue_stub_data(issue) for issue in db.execute(query).scalars()]


def get_issue(db: Session, user: User, essay_id: uuid.UUID, issue_id: uuid.UUID) -> dict:
    return _issue_stub_data(_get_issue(db, user, essay_id, issue_id))


def reveal_issue(db: Session, user: User, essay_id: uuid.UUID, issue_id: uuid.UUID) -> dict:
    issue = _get_issue(db, user, essay_id, issue_id)
    return {
        "issue_id": issue.id,
        "suggestions": [
            {
                "id": s.id,
                "suggested_text": s.suggested_text,
                "explanation": s.explanation,
                "is_recommended": s.is_recommended,
            }
            for s in issue.suggestions
        ],
    }


def ignore_issue(db: Session, user: User, essay_id: uuid.UUID, issue_id: uuid.UUID) -> dict:
    issue = _get_issue(db, user, essay_id, issue_id)
    if issue.status != "detected":
        raise ApiError(409, "VALIDATION_ERROR", "Only detected issues can be ignored.")
    issue.status = "ignored"
    issue.updated_at = utcnow()
    db.commit()
    db.refresh(issue)
    return _issue_stub_data(issue)


def accept_issue_suggestion(
    db: Session, user: User, essay_id: uuid.UUID, issue_id: uuid.UUID, payload
) -> dict:
    """Atomically apply a stored correction (user decision 2026-11-15 §2.5).

    The replacement text comes from the server-stored suggestion, never from
    client input: Working Document update + revision increment + issue
    resolution + suggestion acceptance + Edit Event in one transaction, with
    a base_revision check (AGENTS §4 atomic acceptance invariants).
    """
    essay = get_essay(db, user, essay_id)
    issue = _get_issue(db, user, essay_id, issue_id)
    if issue.status != "detected":
        raise ApiError(409, "VALIDATION_ERROR", "This issue is no longer active.")
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.base_revision:
        raise ApiError(
            409, "WORKING_DOCUMENT_CONFLICT", "The working document changed; reload and retry."
        )
    if issue.source_server_revision != document.server_revision:
        raise ApiError(
            409, "STALE_AI_RESULT", "This issue belongs to an older revision; re-check first."
        )

    suggestion = None
    if payload.suggestion_id is not None:
        suggestion = next((s for s in issue.suggestions if s.id == payload.suggestion_id), None)
        if suggestion is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Suggestion not found for this issue.")
    else:
        suggestion = next((s for s in issue.suggestions if s.is_recommended), None)
        if suggestion is None and issue.suggestions:
            suggestion = issue.suggestions[0]
    if suggestion is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "This issue has no suggestion to accept.")
    if suggestion.status != "pending":
        raise ApiError(409, "VALIDATION_ERROR", "This suggestion was already handled.")

    new_content = tiptap.replace_text_range(
        document.content_json, issue.start_offset, issue.end_offset, suggestion.suggested_text
    )
    new_text, word_count = tiptap.derive_text(new_content)
    now = utcnow()
    old_revision = document.server_revision
    document.content_json = new_content
    document.plain_text = new_text
    document.word_count = word_count
    document.server_revision += 1
    document.content_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
    document.last_saved_at = now
    document.updated_at = now
    essay.updated_at = now

    issue.status = "resolved"
    issue.resolved_by_server_revision = document.server_revision
    issue.updated_at = now
    suggestion.status = "accepted"
    for other in issue.suggestions:
        if other.id != suggestion.id and other.status == "pending":
            other.status = "dismissed"

    stale_others = db.execute(
        select(WritingIssue).where(
            WritingIssue.essay_id == essay_id,
            WritingIssue.status == "detected",
            WritingIssue.source_server_revision == old_revision,
            WritingIssue.id != issue.id,
        )
    ).scalars()
    for other in stale_others:
        other.status = "stale"
        other.updated_at = now

    db.add(
        EssayEditEvent(
            essay_id=essay_id,
            from_server_revision=old_revision,
            to_server_revision=document.server_revision,
            issue_id=issue.id,
            suggestion_id=suggestion.id,
            actor_type="ai_accept",
            event_type="accept_suggestion",
            before_text=issue.anchor_text,
            after_text=suggestion.suggested_text,
            event_metadata={"source": suggestion.source},
            created_at=now,
        )
    )
    db.commit()

    return {
        "issue_id": issue.id,
        "suggestion_id": suggestion.id,
        "server_revision": document.server_revision,
        "applied_text": suggestion.suggested_text,
        "content_json": new_content,
        "plain_text": new_text,
        "word_count": word_count,
    }


def _sentence_around(text: str, offset: int) -> tuple[str, int]:
    """Return (sentence, start_codepoint) containing the offset."""
    start = offset
    while start > 0 and text[start - 1] not in ".!?\n":
        start -= 1
    while start < len(text) and text[start] in " \t":
        start += 1
    end = offset
    while end < len(text) and text[end] not in ".!?\n":
        end += 1
    if end < len(text):
        end += 1
    return text[start:end], start


def validate_issue(
    db: Session, user: User, essay_id: uuid.UUID, payload: IssueValidationRequest
) -> dict:
    essay = get_essay(db, user, essay_id)
    issue = _get_issue(db, user, essay_id, payload.issue_id)
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.base_revision:
        raise ApiError(
            409, "WORKING_DOCUMENT_CONFLICT", "The working document changed; reload and retry."
        )
    if issue.status not in ("detected",):
        raise ApiError(409, "VALIDATION_ERROR", "This issue is no longer active.")
    old_text = document.plain_text
    old_revision = document.server_revision
    original_sentence, _ = _sentence_around(old_text, issue.start_offset)
    db.commit()  # release the read/lock transaction before network judgement

    content_json = tiptap.validate_document(payload.content_json)
    new_text, word_count = tiptap.derive_text(content_json)
    tiptap.check_client_values(payload.plain_text, payload.word_count, new_text, word_count)

    # Rule-first validation: re-check the corrected text. If the same rule
    # still fires anywhere, the issue is unresolved — regardless of where the
    # user edited. Any contextually valid alternative passes (no equality with
    # a single reference answer).
    re_detected, _lt_ok = _run_rule_engine(new_text)
    expected_start = issue.start_offset
    if payload.modified_range.end <= issue.start_offset:
        expected_start += len(new_text) - len(old_text)
    expected_start = max(0, min(expected_start, max(0, len(new_text) - 1)))
    still_present = sorted(
        (d for d in re_detected if d.rule_id == issue.rule_id),
        key=lambda d: abs(d.start_offset - expected_start),
    )
    corrected_sentence, _ = _sentence_around(new_text, expected_start)
    if issue.source == "rule_engine":
        status = "incorrect" if still_present else "correct"
        judgement_usage = None
    else:
        prompt = get_prompt("grammar_validate", "v1")
        user_prompt = prompt.user_template.format(
            original_sentence=original_sentence,
            category=issue.category,
            anchor_text=issue.anchor_text,
            short_explanation=issue.short_explanation or "",
            corrected_sentence=corrected_sentence,
        )
        judgement, judgement_usage = llm.call_llm(
            system=prompt.system, user=user_prompt, response_model=ValidationJudgement
        )
        status = judgement.status

    # Short write transaction with a second revision check (ERD §15.3).
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.base_revision:
        raise ApiError(
            409, "WORKING_DOCUMENT_CONFLICT", "The working document changed during validation."
        )
    now = utcnow()
    document.content_json = content_json
    document.plain_text = new_text
    document.word_count = word_count
    document.server_revision += 1
    document.content_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
    document.last_saved_at = now
    document.updated_at = now
    essay.updated_at = now

    new_revision = document.server_revision
    if status == "correct":
        issue.status = "resolved"
        issue.resolved_by_server_revision = new_revision
    elif status == "incorrect" and still_present:
        # Re-anchor the issue to the new revision so highlighting stays valid.
        match = still_present[0]
        issue.source_server_revision = new_revision
        issue.start_offset = match.start_offset
        issue.end_offset = match.end_offset
        issue.anchor_text = match.anchor_text
        issue.short_explanation = match.short_explanation
    issue.updated_at = now

    # Other detected issues from the old revision are stale after the edit.
    stale_others = db.execute(
        select(WritingIssue).where(
            WritingIssue.essay_id == essay_id,
            WritingIssue.status == "detected",
            WritingIssue.source_server_revision == old_revision,
            WritingIssue.id != issue.id,
        )
    ).scalars()
    for other in stale_others:
        other.status = "stale"
        other.updated_at = now

    db.add(
        EssayEditEvent(
            essay_id=essay_id,
            from_server_revision=old_revision,
            to_server_revision=new_revision,
            issue_id=issue.id,
            actor_type="user",
            event_type="manual_revision",
            before_text=original_sentence,
            after_text=corrected_sentence,
            event_metadata={"validation_status": status},
            created_at=now,
        )
    )
    if judgement_usage is not None:
        llm.record_usage(
            db,
            user_id=user.id,
            feature="grammar_validate",
            usage=judgement_usage,
            prompt_version="v1",
            status="success",
        )
    db.commit()

    return {
        "issue_id": issue.id,
        "validation_status": status,
        "is_resolved": status == "correct",
        "server_revision": new_revision,
    }


def request_teaching(
    db: Session, user: User, essay_id: uuid.UUID, issue_id: uuid.UUID, payload: TeachingRequest
) -> dict:
    get_essay(db, user, essay_id)
    issue = _get_issue(db, user, essay_id, issue_id)
    document = essay_repository.lock_working_document(db, essay_id)
    if document.server_revision != payload.server_revision:
        raise ApiError(
            409, "STALE_AI_RESULT", "The document changed; reload before requesting teaching."
        )
    db.commit()  # no transaction held during the LLM call

    context_snapshot = {
        "current_sentence": payload.current_sentence,
        "paragraph_context": payload.paragraph_context,
        "user_current_text": payload.user_current_text,
        "category": issue.category,
        "anchor_text": issue.anchor_text,
    }
    context_hash = hashlib.sha256(
        repr(sorted(context_snapshot.items())).encode("utf-8")
    ).hexdigest()

    cached = db.execute(
        select(IssueTeaching).where(
            IssueTeaching.issue_id == issue.id,
            IssueTeaching.source_server_revision == payload.server_revision,
            IssueTeaching.context_hash == context_hash,
        )
    ).scalar_one_or_none()
    if cached is not None:
        return _teaching_data(cached)

    prompt = get_prompt("teaching", "v1")
    # No verified weakness history exists yet (user_weaknesses arrives with the
    # learning slice); never fabricate it — personalized_note stays null.
    user_prompt = prompt.user_template.format(
        current_sentence=payload.current_sentence,
        paragraph_context=payload.paragraph_context or "",
        category=issue.category,
        anchor_text=issue.anchor_text,
        user_current_text=payload.user_current_text or "",
        weakness_history="none",
    )
    content, usage = llm.call_llm(
        system=prompt.system, user=user_prompt, response_model=TeachingContent
    )
    personalized_note = None  # enforced until verified weakness data exists

    now = utcnow()
    teaching = IssueTeaching(
        issue_id=issue.id,
        essay_version_id=issue.essay_version_id,
        source_server_revision=payload.server_revision,
        context_hash=context_hash,
        context_snapshot=context_snapshot,
        explanation_json={
            "title": content.title,
            "why_wrong": content.why_wrong,
            "grammar_rule": content.grammar_rule,
            "recommended_correction": content.recommended_correction,
            "personalized_note": personalized_note,
            "examples": content.examples,
            "practice": content.practice,
        },
        model_name=usage.model_name,
        prompt_version=prompt.version,
        created_at=now,
    )
    db.add(teaching)
    llm.record_usage(
        db,
        user_id=user.id,
        feature="teaching",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    db.refresh(teaching)
    return _teaching_data(teaching)


def _teaching_data(teaching: IssueTeaching) -> dict:
    explanation = teaching.explanation_json
    return {
        "teaching_id": teaching.id,
        "issue_id": teaching.issue_id,
        "source_server_revision": teaching.source_server_revision,
        "title": explanation["title"],
        "why_wrong": explanation["why_wrong"],
        "grammar_rule": explanation["grammar_rule"],
        "recommended_correction": explanation["recommended_correction"],
        "personalized_note": explanation.get("personalized_note"),
    }
