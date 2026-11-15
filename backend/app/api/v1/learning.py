"""Learning routes (thin): reviews, progress, summary, weaknesses."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.learning import service
from app.modules.learning.schemas import (
    CreatePlanRequest,
    DueReviewsResponse,
    LearningSummaryResponse,
    PatchTaskRequest,
    PlanListResponse,
    PlanResponse,
    PracticeRequest,
    PracticeResponse,
    ProgressResponse,
    ReviewResultResponse,
    SubmitReviewRequest,
    TaskListResponse,
    TaskResponse,
    WeaknessDetailResponse,
    WeaknessListResponse,
    WeaknessTrendsResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


@router.get("/learning/reviews/due", response_model=DueReviewsResponse)
def due_reviews(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DueReviewsResponse:
    items = service.due_reviews(db, user, limit=limit)
    return DueReviewsResponse.model_validate(
        {
            "data": {"items": items, "due_count": len(items)},
            "meta": {"request_id": new_request_id()},
        }
    )


@router.post("/learning/reviews", status_code=201, response_model=ReviewResultResponse)
def submit_review(
    payload: SubmitReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewResultResponse:
    data = service.submit_review(db, user, payload.expression_id, payload.user_answer)
    return ReviewResultResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


@router.get("/expressions/{expression_id}/progress", response_model=ProgressResponse)
def get_progress(
    expression_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressResponse:
    progress = service.get_progress(db, user, expression_id)
    return ProgressResponse.model_validate(
        {"data": progress, "meta": {"request_id": new_request_id()}}
    )


@router.get("/learning/summary", response_model=LearningSummaryResponse)
def learning_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningSummaryResponse:
    data = service.learning_summary(db, user)
    return LearningSummaryResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


@router.get("/users/me/weaknesses", response_model=WeaknessListResponse)
def list_weaknesses(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeaknessListResponse:
    items = service.list_weaknesses(db, user)
    return WeaknessListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/users/me/weaknesses/trends", response_model=WeaknessTrendsResponse)
def weakness_trends(
    category: str | None = Query(default=None),
    weeks: int = Query(default=4, ge=1, le=12),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeaknessTrendsResponse:
    data = service.weakness_trends(db, user, category, weeks=weeks)
    return WeaknessTrendsResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


@router.get("/users/me/weaknesses/{category}", response_model=WeaknessDetailResponse)
def weakness_detail(
    category: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeaknessDetailResponse:
    data = service.weakness_detail(db, user, category)
    return WeaknessDetailResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


@router.post("/users/me/weaknesses/practice", status_code=202, response_model=PracticeResponse)
def weakness_practice(
    payload: PracticeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticeResponse:
    data = service.generate_practice(db, user, payload.category, payload.count)
    return PracticeResponse.model_validate({"data": data, "meta": {"request_id": new_request_id()}})


@router.post("/learning/plans", status_code=201, response_model=PlanResponse)
def create_plan(
    payload: CreatePlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanResponse:
    plan = service.create_plan(db, user, payload)
    return PlanResponse.model_validate({"data": plan, "meta": {"request_id": new_request_id()}})


@router.get("/learning/plans", response_model=PlanListResponse)
def list_plans(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanListResponse:
    items = service.list_plans(db, user)
    return PlanListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/learning/tasks", response_model=TaskListResponse)
def list_tasks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    items = service.list_tasks(db, user)
    return TaskListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.patch("/learning/tasks/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: uuid.UUID,
    payload: PatchTaskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = service.patch_task(db, user, task_id, payload)
    return TaskResponse.model_validate({"data": task, "meta": {"request_id": new_request_id()}})
