"""AI usage analytics schemas (API Spec §16). User-scoped only."""

from datetime import date

from pydantic import BaseModel

from app.schemas.common import RequestMeta


class UsageTotals(BaseModel):
    total_calls: int
    success_calls: int
    error_calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float


class UsageTotalsResponse(BaseModel):
    data: UsageTotals
    meta: RequestMeta


class FeatureUsage(BaseModel):
    feature: str
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float


class FeatureUsageListData(BaseModel):
    items: list[FeatureUsage]


class FeatureUsageListResponse(BaseModel):
    data: FeatureUsageListData
    meta: RequestMeta


class UsageTrendPoint(BaseModel):
    date: date
    calls: int
    estimated_cost: float


class UsageTrendsData(BaseModel):
    items: list[UsageTrendPoint]


class UsageTrendsResponse(BaseModel):
    data: UsageTrendsData
    meta: RequestMeta
