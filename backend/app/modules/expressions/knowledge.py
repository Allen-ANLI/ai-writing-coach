"""Knowledge/RAG services (SD §8, ERD §9.3, API Spec §9).

- Embeddings are rebuildable; stored with model + content hash.
- Semantic retrieval is ALWAYS scoped to the authenticated user at query time
  (AGENTS §4 / API Spec §18) — never a post-filter on global results.
- Extraction candidates are returned for user confirmation; nothing is saved
  until the user confirms via the expressions create endpoint.
"""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.embeddings import embed_texts
from app.ai.prompts.registry import get_prompt
from app.ai.schemas import ExtractionResult
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing import service as billing_service
from app.modules.essays import repository as essay_repository
from app.modules.essays.service import get_essay
from app.modules.expressions.models import ExpressionEmbedding, UserExpression
from app.modules.users.models import User


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_embedding(db: Session, expression: UserExpression) -> None:
    """Best-effort embedding on create/update. Embeddings are rebuildable, so
    a provider failure must not block knowledge-base writes."""
    text = expression.english_text
    if expression.chinese_meaning:
        text = f"{text} | {expression.chinese_meaning}"
    content_hash = _content_hash(text)
    try:
        result = embed_texts([text])
    except ApiError:
        return
    existing = db.execute(
        select(ExpressionEmbedding).where(
            ExpressionEmbedding.expression_id == expression.id,
            ExpressionEmbedding.embedding_model == result.model_name,
            ExpressionEmbedding.content_hash == content_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        ExpressionEmbedding(
            expression_id=expression.id,
            embedding_model=result.model_name,
            dimensions=len(result.vectors[0]),
            embedding=result.vectors[0],
            content_hash=content_hash,
            created_at=utcnow(),
        )
    )


def semantic_candidates(
    db: Session, user_id: uuid.UUID, text: str, *, limit: int = 5
) -> list[UserExpression]:
    """User-scoped cosine recall over the user's own embeddings."""
    try:
        result = embed_texts([text])
    except ApiError:
        return []
    query_vector = result.vectors[0]
    statement = (
        select(UserExpression)
        .join(
            ExpressionEmbedding,
            ExpressionEmbedding.expression_id == UserExpression.id,
        )
        .where(
            UserExpression.user_id == user_id,
            UserExpression.deleted_at.is_(None),
            UserExpression.status != "archived",
            ExpressionEmbedding.embedding_model == result.model_name,
        )
        .order_by(ExpressionEmbedding.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    return list(db.execute(statement).scalars())


def extract_expressions(
    db: Session, user: User, essay_id: uuid.UUID, version_id: uuid.UUID, scope: str
) -> dict:
    """Extract learning candidates from an IMMUTABLE version (API Spec §9).

    Returns candidates for confirmation; persistence happens only when the
    user saves them via POST /expressions.
    """
    get_essay(db, user, essay_id)
    version = essay_repository.get_version_for_essay(db, essay_id, version_id)
    if version is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Version not found.")
    if scope not in ("full", "assisted_changes"):
        raise ApiError(
            422, "VALIDATION_ERROR", "extraction_scope must be full or assisted_changes."
        )
    db.commit()  # no transaction held during the LLM call

    prompt = get_prompt("learning_extract", "v1")
    user_prompt = prompt.user_template.format(scope=scope, essay_text=version.plain_text)
    billing_service.guard_ai_call(db, user.id)
    result, usage = llm.call_llm(
        system=prompt.system, user=user_prompt, response_model=ExtractionResult
    )
    llm.record_usage(
        db,
        user_id=user.id,
        feature="learning_extract",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()

    return {
        "essay_id": essay_id,
        "version_id": version_id,
        "extraction_scope": scope,
        "candidates": [candidate.model_dump() for candidate in result.candidates],
    }
