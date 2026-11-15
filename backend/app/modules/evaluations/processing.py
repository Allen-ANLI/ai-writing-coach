"""Background processing for queued evaluations and rewrites.

Runs after the 202 response via FastAPI BackgroundTasks, with its own session
from the app's session factory (tests inject the isolated test factory). The
LLM call happens OUTSIDE any DB transaction (AGENTS §4); results are persisted
in a short transaction afterwards. Bands are normalized to half-band steps and
the overall band is computed server-side — never taken from the LLM.
"""

import logging
import math
import uuid
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from app.ai import llm
from app.ai.prompts.registry import get_prompt
from app.ai.providers.base import LlmUsage
from app.ai.schemas import (
    GeneralEvaluationResult,
    IeltsTask1EvaluationResult,
    IeltsTask2EvaluationResult,
    RewriteResult,
)
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.essays.models import Essay, EssayVersion
from app.modules.evaluations.models import EssayEvaluation, EssayRewrite

logger = logging.getLogger(__name__)


def _half_band(value: float) -> float:
    return math.floor(value * 2 + 0.5) / 2


def _criteria(result) -> dict[str, dict]:
    scores = {}
    for name, value in result.model_dump().items():
        if isinstance(value, dict) and "band" in value:
            scores[name] = {"band": _half_band(value["band"]), "feedback": value["feedback"]}
    return scores


def _feedback(result) -> dict:
    return {
        "overall_feedback": result.overall_feedback,
        "strengths": result.strengths,
        "improvements": result.improvements,
    }


def _plain_text_to_doc(text: str) -> dict:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs
        ],
    }


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


def process_evaluation(session_factory: sessionmaker, evaluation_id: uuid.UUID) -> None:
    with session_factory() as db:
        evaluation = db.get(EssayEvaluation, evaluation_id)
        if evaluation is None or evaluation.status != "queued":
            return
        evaluation.status = "processing"
        evaluation.started_at = utcnow()
        db.commit()

        version = db.get(EssayVersion, evaluation.version_id)
        essay = db.get(Essay, evaluation.essay_id)
        if version is None or essay is None:
            evaluation.status = "failed"
            evaluation.error_message = "Source version no longer exists."
            evaluation.completed_at = utcnow()
            db.commit()
            return

        if evaluation.evaluation_type == "ielts":
            feature = (
                "ielts_evaluate_task1"
                if evaluation.task_type == "task1"
                else "ielts_evaluate_task2"
            )
            response_model = (
                IeltsTask1EvaluationResult
                if evaluation.task_type == "task1"
                else IeltsTask2EvaluationResult
            )
        else:
            feature = "general_evaluate"
            response_model = GeneralEvaluationResult
        prompt = get_prompt(feature, "v1")
        user_message = prompt.user_template.format(
            question_prompt=essay.question_prompt or "(free writing)",
            word_count=version.word_count,
            essay_text=version.plain_text,
        )

        try:
            result, usage = llm.call_llm(
                system=prompt.system, user=user_message, response_model=response_model
            )
        except ApiError as exc:
            evaluation.status = "failed"
            evaluation.error_message = exc.message
            evaluation.completed_at = utcnow()
            llm.record_usage(
                db,
                user_id=evaluation.user_id,
                feature=feature,
                usage=_error_usage(),
                prompt_version=prompt.version,
                status="error",
            )
            db.commit()
            return
        except Exception:
            logger.exception("evaluation %s failed unexpectedly", evaluation_id)
            evaluation.status = "failed"
            evaluation.error_message = "Evaluation failed unexpectedly."
            evaluation.completed_at = utcnow()
            db.commit()
            return

        criteria = _criteria(result)
        overall = _half_band(sum(c["band"] for c in criteria.values()) / len(criteria))
        evaluation.criteria_scores = criteria
        evaluation.feedback_json = _feedback(result)
        evaluation.overall_band = Decimal(str(overall))
        evaluation.is_estimate = True
        evaluation.model_name = usage.model_name
        evaluation.prompt_version = prompt.version
        evaluation.status = "completed"
        evaluation.completed_at = utcnow()
        llm.record_usage(
            db,
            user_id=evaluation.user_id,
            feature=feature,
            usage=usage,
            prompt_version=prompt.version,
            status="success",
        )
        db.commit()


def process_rewrite(session_factory: sessionmaker, rewrite_id: uuid.UUID) -> None:
    with session_factory() as db:
        rewrite = db.get(EssayRewrite, rewrite_id)
        if rewrite is None or rewrite.status != "queued":
            return
        rewrite.status = "processing"
        db.commit()

        version = db.get(EssayVersion, rewrite.source_version_id)
        evaluation = db.get(EssayEvaluation, rewrite.evaluation_id)
        essay = db.get(Essay, evaluation.essay_id) if evaluation else None
        if version is None or essay is None:
            rewrite.status = "failed"
            rewrite.error_message = "Source version no longer exists."
            rewrite.completed_at = utcnow()
            db.commit()
            return

        prompt = get_prompt("rewrite", "v1")
        user_message = prompt.user_template.format(
            modification_level=rewrite.modification_level,
            question_prompt=essay.question_prompt or "(free writing)",
            essay_text=version.plain_text,
        )
        try:
            result, usage = llm.call_llm(
                system=prompt.system, user=user_message, response_model=RewriteResult
            )
        except ApiError as exc:
            rewrite.status = "failed"
            rewrite.error_message = exc.message
            rewrite.completed_at = utcnow()
            llm.record_usage(
                db,
                user_id=evaluation.user_id,
                feature="rewrite",
                usage=_error_usage(),
                prompt_version=prompt.version,
                status="error",
            )
            db.commit()
            return
        except Exception:
            logger.exception("rewrite %s failed unexpectedly", rewrite_id)
            rewrite.status = "failed"
            rewrite.error_message = "Rewrite failed unexpectedly."
            rewrite.completed_at = utcnow()
            db.commit()
            return

        text = result.rewritten_text.strip()
        rewrite.result_content_json = _plain_text_to_doc(text)
        rewrite.result_plain_text = text
        rewrite.change_summary = result.change_summary
        rewrite.model_name = usage.model_name
        rewrite.status = "completed"
        rewrite.completed_at = utcnow()
        llm.record_usage(
            db,
            user_id=evaluation.user_id,
            feature="rewrite",
            usage=usage,
            prompt_version=prompt.version,
            status="success",
        )
        db.commit()
