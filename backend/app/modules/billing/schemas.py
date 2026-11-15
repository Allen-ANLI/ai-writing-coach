"""Billing API schemas (contract 1.3.0, reconciliation R8)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta


class PlanData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    price_monthly: Decimal
    currency: str
    features: dict
    quota_ai_calls_monthly: int | None
    quota_evaluations_monthly: int | None


class PlanListData(BaseModel):
    items: list[PlanData]


class PlanListResponse(BaseModel):
    data: PlanListData
    meta: RequestMeta


class SubscriptionData(BaseModel):
    plan_code: str
    plan_name: str
    status: str
    started_at: datetime
    current_period_start: datetime
    current_period_end: datetime
    cancelled_at: datetime | None


class SubscriptionResponse(BaseModel):
    data: SubscriptionData
    meta: RequestMeta


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=1, max_length=30)


class CheckoutData(BaseModel):
    transaction_id: uuid.UUID
    plan_code: str
    amount: Decimal
    currency: str
    provider: str
    status: str


class CheckoutResponse(BaseModel):
    data: CheckoutData
    meta: RequestMeta


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: uuid.UUID


class TransactionData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    provider: str
    provider_ref: str
    amount: Decimal
    currency: str
    status: str
    kind: str
    created_at: datetime
    completed_at: datetime | None


class HistoryListData(BaseModel):
    items: list[TransactionData]


class HistoryListResponse(BaseModel):
    data: HistoryListData
    meta: RequestMeta


class UsageData(BaseModel):
    plan_code: str
    period_start: str
    ai_calls: int
    evaluations: int
    quota_ai_calls_monthly: int | None
    quota_evaluations_monthly: int | None


class UsageResponse(BaseModel):
    data: UsageData
    meta: RequestMeta
