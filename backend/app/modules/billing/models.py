"""Billing models (ERD V1.2.4 §16, migration 0016).

One subscription per user; free tier materialized lazily. usage_meters counts
actual LLM calls and queued evaluations per calendar month. Payment provider
is constrained to 'sandbox' at the DB level until activation is approved.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.infrastructure.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        CheckConstraint("price_monthly >= 0", name="ck_subscription_plans_price"),
        UniqueConstraint("code", name="uq_subscription_plans_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quota_ai_calls_monthly: Mapped[int | None] = mapped_column(Integer)
    quota_evaluations_monthly: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'cancelled', 'expired', 'past_due')",
            name="ck_user_subscriptions_status",
        ),
        UniqueConstraint("user_id", name="uq_user_subscriptions_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class UsageMeter(Base):
    __tablename__ = "usage_meters"
    __table_args__ = (
        CheckConstraint("ai_calls >= 0", name="ck_usage_meters_ai_calls"),
        CheckConstraint("evaluations >= 0", name="ck_usage_meters_evaluations"),
        UniqueConstraint("user_id", "period_start", name="uq_usage_meters_user_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    ai_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        CheckConstraint("provider IN ('sandbox')", name="ck_payment_transactions_provider"),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'refunded')",
            name="ck_payment_transactions_status",
        ),
        CheckConstraint("kind IN ('subscription', 'refund')", name="ck_payment_transactions_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="sandbox")
    provider_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="subscription")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
