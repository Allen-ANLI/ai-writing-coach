"""Learning business logic (API Spec §10–11, PRD FR-05/FR-07).

- Review prompts never leak the English answer (due list shows Chinese).
- Answer judging: rule-first (normalized exact match passes without LLM);
  otherwise the LLM judges semantic equivalence — any natural correct
  translation is accepted, not only the reference wording.
- Intervals/mastery are deterministic SM-2 (sm2.py), never LLM-decided.
- Weakness trends are volume-adjusted (errors per 1000 words), not raw counts.
"""

import json
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.prompts.registry import get_prompt
from app.ai.schemas import PracticeResult, ReviewJudgement
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing import service as billing_service
from app.modules.expressions.models import UserExpression
from app.modules.grammar.models import WritingIssue
from app.modules.learning import sm2
from app.modules.learning.models import (
    ExpressionProgress,
    ExpressionReview,
    LearningPlan,
    LearningTask,
    UserWeakness,
)
from app.modules.learning.schemas import CreatePlanRequest, PatchTaskRequest
from app.modules.users.models import User


def _normalize(text: str) -> str:
    return " ".join(text.lower().split()).strip(" .!?")


def _get_expression(db: Session, user: User, expression_id: uuid.UUID) -> UserExpression:
    expression = db.execute(
        select(UserExpression).where(
            UserExpression.id == expression_id,
            UserExpression.user_id == user.id,
            UserExpression.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if expression is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Expression not found.")
    return expression


def _get_or_create_progress(
    db: Session, user: User, expression: UserExpression
) -> ExpressionProgress:
    progress = db.execute(
        select(ExpressionProgress).where(
            ExpressionProgress.user_id == user.id,
            ExpressionProgress.expression_id == expression.id,
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = ExpressionProgress(
            user_id=user.id,
            expression_id=expression.id,
            status="learning",
            ease_factor=sm2.INITIAL_EASE,
            updated_at=utcnow(),
        )
        db.add(progress)
        db.flush()
    return progress


def due_reviews(db: Session, user: User, *, limit: int = 20) -> list[dict]:
    now = utcnow()
    statement = (
        select(UserExpression, ExpressionProgress)
        .outerjoin(
            ExpressionProgress,
            (ExpressionProgress.expression_id == UserExpression.id)
            & (ExpressionProgress.user_id == user.id),
        )
        .where(
            UserExpression.user_id == user.id,
            UserExpression.deleted_at.is_(None),
            UserExpression.status.not_in(["archived", "mastered"]),
        )
        .where(
            (ExpressionProgress.id.is_(None))
            | (ExpressionProgress.next_review_at.is_(None))
            | (ExpressionProgress.next_review_at <= now)
        )
        .order_by(ExpressionProgress.next_review_at.asc().nulls_first())
        .limit(limit)
    )
    items = []
    for expression, progress in db.execute(statement).all():
        items.append(
            {
                "expression_id": expression.id,
                "chinese_meaning": expression.chinese_meaning,
                "topic": expression.topic,
                "usage_context": expression.usage_context,
                "status": progress.status if progress else "collected",
                "next_review_at": progress.next_review_at if progress else None,
                "review_count": progress.review_count if progress else 0,
            }
        )
    return items


def submit_review(db: Session, user: User, expression_id: uuid.UUID, user_answer: str) -> dict:
    expression = _get_expression(db, user, expression_id)
    progress = _get_or_create_progress(db, user, expression)
    reference = expression.english_text
    db.commit()  # no transaction held during the LLM call

    # Rule-first: normalized exact match passes without any LLM call.
    if _normalize(user_answer) == _normalize(reference):
        is_correct, score, feedback, usage = True, Decimal("5"), None, None
    else:
        billing_service.guard_ai_call(db, user.id)
        prompt = get_prompt("review_judge", "v1")
        user_prompt = prompt.user_template.format(
            chinese_prompt=expression.chinese_meaning or expression.usage_context or "",
            reference_expression=reference,
            user_answer=user_answer,
        )
        judgement, usage = llm.call_llm(
            system=prompt.system, user=user_prompt, response_model=ReviewJudgement
        )
        is_correct = judgement.is_correct
        score = Decimal(str(judgement.score))
        feedback = judgement.feedback

    quality = int(score) if is_correct else max(0, min(2, int(score)))
    state = sm2.Sm2State(
        interval_days=progress.interval_days,
        ease_factor=progress.ease_factor or sm2.INITIAL_EASE,
        streak=progress.streak_count,
        repetitions=progress.review_count,
    )
    update = sm2.review(state, quality)

    now = utcnow()
    progress.review_count += 1
    progress.streak_count = update.streak
    progress.interval_days = update.interval_days
    progress.ease_factor = update.ease_factor
    progress.last_reviewed_at = now
    progress.next_review_at = now + timedelta(days=float(update.interval_days))
    progress.updated_at = now
    if is_correct:
        progress.correct_count += 1
    else:
        progress.incorrect_count += 1
    if update.mastered:
        progress.status = "mastered"
        expression.status = "mastered"
    elif progress.review_count >= 2:
        progress.status = "reviewing"
        expression.status = "reviewing"
    else:
        progress.status = "learning"
        expression.status = "learning"

    db.add(
        ExpressionReview(
            progress_id=progress.id,
            user_answer=user_answer,
            reference_expression=reference,
            is_correct=is_correct,
            score=score,
            feedback_json=(
                json.dumps({"feedback": feedback}, ensure_ascii=False) if feedback else None
            ),
            reviewed_at=now,
        )
    )
    if usage is not None:
        llm.record_usage(
            db,
            user_id=user.id,
            feature="review_judge",
            usage=usage,
            prompt_version="v1",
            status="success",
        )
    db.commit()

    return {
        "expression_id": expression.id,
        "is_correct": is_correct,
        "score": score,
        "feedback": feedback,
        "reference_expression": reference,
        "status": progress.status,
        "interval_days": update.interval_days,
        "next_review_at": progress.next_review_at,
        "streak_count": update.streak,
    }


def get_progress(db: Session, user: User, expression_id: uuid.UUID) -> ExpressionProgress:
    expression = _get_expression(db, user, expression_id)
    return _get_or_create_progress(db, user, expression)


def learning_summary(db: Session, user: User) -> dict:
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    expressions = list(
        db.execute(
            select(UserExpression).where(
                UserExpression.user_id == user.id, UserExpression.deleted_at.is_(None)
            )
        ).scalars()
    )
    by_status: dict[str, int] = {}
    for expression in expressions:
        by_status[expression.status] = by_status.get(expression.status, 0) + 1

    due_count = len(due_reviews(db, user, limit=1000))
    reviewed_today = db.execute(
        select(func.count(ExpressionReview.id))
        .join(ExpressionProgress, ExpressionProgress.id == ExpressionReview.progress_id)
        .where(ExpressionProgress.user_id == user.id, ExpressionReview.reviewed_at >= today_start)
    ).scalar_one()
    total_reviews = db.execute(
        select(func.count(ExpressionReview.id))
        .join(ExpressionProgress, ExpressionProgress.id == ExpressionReview.progress_id)
        .where(ExpressionProgress.user_id == user.id)
    ).scalar_one()

    return {
        "total_expressions": len(expressions),
        "by_status": by_status,
        "due_now": due_count,
        "reviewed_today": reviewed_today,
        "mastered": by_status.get("mastered", 0),
        "total_reviews": total_reviews,
    }


def record_weakness_occurrence(
    db: Session, user_id: uuid.UUID, category: str, sub_category: str | None
) -> None:
    """Called when an issue is detected; keeps the aggregate profile current."""
    sub = sub_category or ""
    weakness = db.execute(
        select(UserWeakness).where(
            UserWeakness.user_id == user_id,
            UserWeakness.category == category,
            UserWeakness.sub_category == sub,
        )
    ).scalar_one_or_none()
    now = utcnow()
    if weakness is None:
        weakness = UserWeakness(
            user_id=user_id,
            category=category,
            sub_category=sub,
            total_occurrences=0,
            recent_occurrences=0,
            updated_at=now,
        )
        db.add(weakness)
    weakness.total_occurrences += 1
    weakness.recent_occurrences += 1
    weakness.last_occurred_at = now
    weakness.updated_at = now


def list_weaknesses(db: Session, user: User) -> list[UserWeakness]:
    return list(
        db.execute(
            select(UserWeakness)
            .where(UserWeakness.user_id == user.id)
            .order_by(UserWeakness.total_occurrences.desc())
        ).scalars()
    )


def weakness_detail(db: Session, user: User, category: str) -> dict:
    weaknesses = [w for w in list_weaknesses(db, user) if w.category == category]
    if not weaknesses:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "No weakness profile for this category.")
    examples = list(
        db.execute(
            select(WritingIssue)
            .where(WritingIssue.user_id == user.id, WritingIssue.category == category)
            .order_by(WritingIssue.created_at.desc())
            .limit(5)
        ).scalars()
    )
    return {
        "category": category,
        "total_occurrences": sum(w.total_occurrences for w in weaknesses),
        "recent_occurrences": sum(w.recent_occurrences for w in weaknesses),
        "trend": weaknesses[0].trend,
        "examples": [
            {
                "essay_id": issue.essay_id,
                "anchor_text": issue.anchor_text,
                "short_explanation": issue.short_explanation,
                "created_at": issue.created_at,
            }
            for issue in examples
        ],
    }


def weakness_trends(db: Session, user: User, category: str | None, *, weeks: int = 4) -> dict:
    """Volume-adjusted trend: errors per 1000 words per weekly bucket.

    Writing volume proxy: sum of word_count of essay versions created in the
    bucket (snapshots mark writing activity). Buckets with zero words yield
    null density rather than a misleading infinity.
    """
    from app.modules.essays.models import EssayVersion

    now = utcnow()
    points = []
    for offset in range(weeks - 1, -1, -1):
        period_end = now - timedelta(weeks=offset)
        period_start = period_end - timedelta(weeks=1)
        issue_query = select(func.count(WritingIssue.id)).where(
            WritingIssue.user_id == user.id,
            WritingIssue.created_at >= period_start,
            WritingIssue.created_at < period_end,
        )
        if category:
            issue_query = issue_query.where(WritingIssue.category == category)
        issues = db.execute(issue_query).scalar_one()

        words = db.execute(
            select(func.coalesce(func.sum(EssayVersion.word_count), 0)).where(
                EssayVersion.created_by == user.id,
                EssayVersion.created_at >= period_start,
                EssayVersion.created_at < period_end,
            )
        ).scalar_one()

        density = (
            (Decimal(issues) / Decimal(words) * Decimal(1000)).quantize(Decimal("0.01"))
            if words
            else None
        )
        points.append(
            {
                "period_start": period_start,
                "issues": issues,
                "words_written": words,
                "errors_per_1000_words": density,
            }
        )
    return {
        "category": category,
        "points": points,
        "methodology": (
            "Weekly buckets; errors per 1000 words written (version word_count sum). "
            "Null density when no writing volume in the bucket."
        ),
    }


def generate_practice(db: Session, user: User, category: str, count: int) -> dict:
    db.commit()  # no transaction held during the LLM call
    billing_service.guard_ai_call(db, user.id)
    prompt = get_prompt("weakness_practice", "v1")
    user_prompt = prompt.user_template.format(category=category, count=count)
    result, usage = llm.call_llm(
        system=prompt.system, user=user_prompt, response_model=PracticeResult
    )
    llm.record_usage(
        db,
        user_id=user.id,
        feature="weakness_practice",
        usage=usage,
        prompt_version=prompt.version,
        status="success",
    )
    db.commit()
    return {
        "category": category,
        "items": [item.model_dump() for item in result.items[:count]],
    }


def create_plan(db: Session, user: User, payload: CreatePlanRequest) -> LearningPlan:
    if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
        raise ApiError(422, "VALIDATION_ERROR", "end_date must not be before start_date.")
    plan = LearningPlan(
        user_id=user.id,
        title=payload.title,
        goal=payload.goal,
        daily_target_minutes=payload.daily_target_minutes,
        status="active",
        start_date=payload.start_date,
        end_date=payload.end_date,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def list_plans(db: Session, user: User) -> list[LearningPlan]:
    rows = db.execute(
        select(LearningPlan)
        .where(LearningPlan.user_id == user.id)
        .order_by(LearningPlan.created_at.desc(), LearningPlan.id.desc())
    ).scalars()
    return list(rows)


def list_tasks(db: Session, user: User) -> list[LearningTask]:
    rows = db.execute(
        select(LearningTask)
        .where(LearningTask.user_id == user.id)
        .order_by(LearningTask.scheduled_at.asc().nulls_last(), LearningTask.created_at.desc())
    ).scalars()
    return list(rows)


def patch_task(
    db: Session, user: User, task_id: uuid.UUID, payload: PatchTaskRequest
) -> LearningTask:
    task = db.execute(
        select(LearningTask).where(LearningTask.id == task_id, LearningTask.user_id == user.id)
    ).scalar_one_or_none()
    if task is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Task not found.")
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        task.status = updates["status"]
        task.completed_at = utcnow() if updates["status"] == "completed" else None
    if "title" in updates:
        task.title = updates["title"]
    if "description" in updates:
        task.description = updates["description"]
    if "scheduled_at" in updates:
        task.scheduled_at = updates["scheduled_at"]
    db.commit()
    db.refresh(task)
    return task


def create_plan_from_suggestions(
    db: Session, user: User, goal: str | None, suggestions: list[dict], workflow_id: uuid.UUID
) -> LearningPlan:
    """Study-planner confirmation: deterministic plan + one task per suggestion.

    Scheduling/counts stay rule-based (SD §9.3): tasks are unscheduled
    pending items; SM-2 continues to own review timing.
    """
    plan = LearningPlan(
        user_id=user.id,
        title="Personalized study plan",
        goal=goal,
        status="active",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(plan)
    db.flush()
    for suggestion in suggestions:
        db.add(
            LearningTask(
                plan_id=plan.id,
                user_id=user.id,
                task_type=suggestion["task_type"],
                title=suggestion["title"][:255],
                description=suggestion.get("description"),
                status="pending",
                event_metadata={"workflow_id": str(workflow_id)},
                created_at=utcnow(),
            )
        )
    db.commit()
    db.refresh(plan)
    return plan
