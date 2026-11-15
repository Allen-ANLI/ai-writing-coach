"""AI usage analytics routes (thin, user-scoped)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.analytics import service
from app.modules.analytics.schemas import (
    FeatureUsageListResponse,
    UsageTotalsResponse,
    UsageTrendsResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


@router.get("/analytics/ai-usage", response_model=UsageTotalsResponse)
def ai_usage(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageTotalsResponse:
    return UsageTotalsResponse.model_validate(
        {"data": service.usage_totals(db, user), "meta": {"request_id": new_request_id()}}
    )


@router.get("/analytics/ai-usage/by-feature", response_model=FeatureUsageListResponse)
def ai_usage_by_feature(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeatureUsageListResponse:
    items = service.usage_by_feature(db, user)
    return FeatureUsageListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/analytics/ai-usage/trends", response_model=UsageTrendsResponse)
def ai_usage_trends(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageTrendsResponse:
    items = service.usage_trends(db, user)
    return UsageTrendsResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )
