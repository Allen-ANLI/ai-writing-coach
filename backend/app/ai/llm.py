"""LLM service: provider selection, structured-output validation, usage logging.

Callers MUST invoke call_llm outside long DB transactions (AGENTS §4), then
persist results and record_usage in a short transaction.
"""

import uuid

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.providers.base import LlmError, LlmProvider, LlmUsage
from app.ai.providers.mock import MockProvider
from app.ai.providers.openai_compat import OpenAiCompatProvider
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.modules.analytics.models import AiUsageLog


def get_provider() -> LlmProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockProvider()
    if settings.llm_provider == "openai_compat":
        return OpenAiCompatProvider()
    raise ApiError(500, "LLM_PROVIDER_ERROR", f"Unknown LLM provider: {settings.llm_provider}")


def call_llm(
    *,
    system: str,
    user: str,
    response_model: type[BaseModel],
) -> tuple[BaseModel, LlmUsage]:
    provider = get_provider()
    try:
        result = provider.complete_json(system=system, user=user, response_model=response_model)
    except LlmError as exc:
        if exc.timeout:
            raise ApiError(504, "LLM_TIMEOUT", "The AI service timed out.") from exc
        raise ApiError(502, "LLM_PROVIDER_ERROR", "The AI service failed.") from exc
    try:
        parsed = response_model.model_validate(result.content_json)
    except ValidationError as exc:
        raise ApiError(
            502, "LLM_PROVIDER_ERROR", "The AI service returned an invalid structure."
        ) from exc
    return parsed, result.usage


def record_usage(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    feature: str,
    usage: LlmUsage,
    prompt_version: str | None,
    status: str,
    trace_id: str | None = None,
) -> AiUsageLog:
    """Add a usage log row; the caller commits with its own short transaction."""
    log = AiUsageLog(
        user_id=user_id,
        feature=feature,
        provider=usage.provider,
        model_name=usage.model_name,
        prompt_version=prompt_version,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        latency_ms=usage.latency_ms,
        estimated_cost=usage.estimated_cost,
        status=status,
        trace_id=trace_id,
    )
    db.add(log)
    return log
