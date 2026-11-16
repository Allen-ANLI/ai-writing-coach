"""Background outline generation (LLM outside DB transactions, AGENTS §4)."""

import logging
import uuid

from sqlalchemy.orm import sessionmaker

from app.ai import llm
from app.ai.prompts.registry import get_prompt
from app.ai.providers.base import LlmUsage
from app.ai.schemas import OutlineGenerationResult
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.essays.models import Essay
from app.modules.expressions import knowledge
from app.modules.outlines import service
from app.modules.outlines.models import WritingOutline

logger = logging.getLogger(__name__)


def process_outline_generation(session_factory: sessionmaker, outline_id: uuid.UUID) -> None:
    with session_factory() as db:
        outline = db.get(WritingOutline, outline_id)
        if outline is None or outline.status != "generating":
            return
        essay = db.get(Essay, outline.essay_id)
        if essay is None:
            outline.status = "failed"
            outline.updated_at = utcnow()
            db.commit()
            return

        context = outline.source_context or {}
        viewpoint = context.get("viewpoint") or outline.thesis_statement or "(not provided)"
        question_prompt = (
            essay.question_prompt or context.get("question_prompt") or "(free writing)"
        )
        recalled = knowledge.semantic_candidates(db, outline.user_id, str(viewpoint), limit=5)
        previously_learned = "; ".join(e.english_text for e in recalled) or "(none)"
        db.commit()  # no transaction held during the LLM call

        # v3: Chinese guidance, English thesis, AI-chosen structure (ADR-029).
        prompt = get_prompt("outline_generate", "v3")
        user_message = prompt.user_template.format(
            question_prompt=question_prompt,
            viewpoint=viewpoint,
            instructions=context.get("instructions") or "(none)",
            previously_learned=previously_learned,
        )
        try:
            result, usage = llm.call_llm(
                system=prompt.system, user=user_message, response_model=OutlineGenerationResult
            )
        except ApiError as exc:
            outline.status = "failed"
            outline.updated_at = utcnow()
            llm.record_usage(
                db,
                user_id=outline.user_id,
                feature="outline_generate",
                usage=_error_usage(),
                prompt_version=prompt.version,
                status="error",
            )
            db.commit()
            logger.info("outline %s failed: %s", outline_id, exc.message)
            return
        except Exception:
            logger.exception("outline %s failed unexpectedly", outline_id)
            outline.status = "failed"
            outline.updated_at = utcnow()
            db.commit()
            return

        service.save_generated_outline(
            db,
            outline,
            result.thesis_statement,
            [section.model_dump() for section in result.sections],
        )
        llm.record_usage(
            db,
            user_id=outline.user_id,
            feature="outline_generate",
            usage=usage,
            prompt_version=prompt.version,
            status="success",
        )
        db.commit()


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
