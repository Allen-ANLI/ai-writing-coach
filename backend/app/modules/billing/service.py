"""Billing business logic + quota enforcement (ADR-021).

- Sandbox payments only: checkout creates a pending transaction; confirm
  simulates the provider callback and activates the subscription. Real
  provider activation requires explicit user approval (Directive §6/§10).
- Quotas are per calendar month. NULL limit = unlimited. Guards run right
  before an LLM call would happen; metering happens in llm.record_usage so
  pure rule checks never consume quota (SD §12.4).
- Free tier is materialized lazily; cancelled subscriptions keep access until
  the period end, then roll back to free on next access.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing.models import (
    PaymentTransaction,
    SubscriptionPlan,
    UsageMeter,
    UserSubscription,
)
from app.modules.billing.schemas import PlanData, SubscriptionData, UsageData

FREE_PLAN_CODE = "free"


def _free_quotas_disabled() -> bool:
    """Temporary exemption (2026-11-16 user directive): free users are not
    quota-limited. Metering still counts every call for analytics."""
    return get_settings().free_plan_quotas_disabled


def _period_start(moment: datetime) -> date:
    return moment.date().replace(day=1)


def _next_month_start(moment: datetime) -> datetime:
    start = _period_start(moment)
    if start.month == 12:
        return datetime(start.year + 1, 1, 1, tzinfo=moment.tzinfo)
    return datetime(start.year, start.month + 1, 1, tzinfo=moment.tzinfo)


def _free_plan(db: Session) -> SubscriptionPlan:
    plan = db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.code == FREE_PLAN_CODE)
    ).scalar_one()
    return plan


def get_or_create_subscription(
    db: Session, user_id: uuid.UUID
) -> tuple[UserSubscription, SubscriptionPlan]:
    now = utcnow()
    row = db.execute(
        select(UserSubscription).where(UserSubscription.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        # Concurrent requests may race here (page loads fire several billing
        # queries at once); ON CONFLICT makes creation atomic.
        plan = _free_plan(db)
        db.execute(
            pg_insert(UserSubscription)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                plan_id=plan.id,
                status="active",
                started_at=now,
                current_period_start=_period_start(now),
                current_period_end=_next_month_start(now),
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        db.commit()
        row = db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        ).scalar_one()
        return row, db.get(SubscriptionPlan, row.plan_id)

    plan = db.get(SubscriptionPlan, row.plan_id)
    if now >= row.current_period_end:
        # Sandbox renewal: roll the period; cancelled paid plans drop to free.
        if row.status == "cancelled" and plan.code != FREE_PLAN_CODE:
            plan = _free_plan(db)
            row.plan_id = plan.id
            row.started_at = now
        row.status = "active"
        row.cancelled_at = None
        row.current_period_start = _period_start(now)
        row.current_period_end = _next_month_start(now)
        row.updated_at = now
        db.commit()
        db.refresh(row)
    return row, plan


def _meter(db: Session, user_id: uuid.UUID) -> UsageMeter:
    period = _period_start(utcnow())
    # Atomic upsert: concurrent LLM calls must not race on meter creation.
    db.execute(
        pg_insert(UsageMeter)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            period_start=period,
            ai_calls=0,
            evaluations=0,
            updated_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["user_id", "period_start"])
    )
    return db.execute(
        select(UsageMeter).where(UsageMeter.user_id == user_id, UsageMeter.period_start == period)
    ).scalar_one()


def guard_ai_call(db: Session, user_id: uuid.UUID) -> None:
    _, plan = get_or_create_subscription(db, user_id)
    if plan.quota_ai_calls_monthly is None:
        return
    if plan.code == FREE_PLAN_CODE and _free_quotas_disabled():
        return
    meter = _meter(db, user_id)
    if meter.ai_calls >= plan.quota_ai_calls_monthly:
        raise ApiError(
            429, "QUOTA_EXCEEDED", "Monthly AI call quota reached. Upgrade your plan to continue."
        )


def guard_evaluation(db: Session, user_id: uuid.UUID) -> None:
    _, plan = get_or_create_subscription(db, user_id)
    if plan.quota_evaluations_monthly is None:
        return
    if plan.code == FREE_PLAN_CODE and _free_quotas_disabled():
        return
    meter = _meter(db, user_id)
    if meter.evaluations >= plan.quota_evaluations_monthly:
        raise ApiError(
            429,
            "QUOTA_EXCEEDED",
            "Monthly evaluation quota reached. Upgrade your plan to continue.",
        )


def meter_ai_call(db: Session, user_id: uuid.UUID | None) -> None:
    """Called from llm.record_usage for every actual LLM call."""
    if user_id is None:
        return
    _meter(db, user_id)
    db.execute(
        update(UsageMeter)
        .where(UsageMeter.user_id == user_id, UsageMeter.period_start == _period_start(utcnow()))
        .values(ai_calls=UsageMeter.ai_calls + 1, updated_at=utcnow())
    )


def meter_evaluation(db: Session, user_id: uuid.UUID) -> None:
    _meter(db, user_id)
    db.execute(
        update(UsageMeter)
        .where(UsageMeter.user_id == user_id, UsageMeter.period_start == _period_start(utcnow()))
        .values(evaluations=UsageMeter.evaluations + 1, updated_at=utcnow())
    )


def list_plans(db: Session) -> list[PlanData]:
    rows = db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.price_monthly.asc())
    ).scalars()
    plans = [PlanData.model_validate(row) for row in rows]
    if _free_quotas_disabled():
        plans = [
            plan.model_copy(
                update={"quota_ai_calls_monthly": None, "quota_evaluations_monthly": None}
            )
            if plan.code == FREE_PLAN_CODE
            else plan
            for plan in plans
        ]
    return plans


def subscription_data(db: Session, user_id: uuid.UUID) -> SubscriptionData:
    subscription, plan = get_or_create_subscription(db, user_id)
    return SubscriptionData(
        plan_code=plan.code,
        plan_name=plan.name,
        status=subscription.status,
        started_at=subscription.started_at,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancelled_at=subscription.cancelled_at,
    )


def checkout(db: Session, user_id: uuid.UUID, plan_code: str) -> PaymentTransaction:
    plan = db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.code == plan_code, SubscriptionPlan.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if plan is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Plan not found.")
    if plan.code == FREE_PLAN_CODE:
        raise ApiError(422, "VALIDATION_ERROR", "The free plan does not require checkout.")
    transaction = PaymentTransaction(
        user_id=user_id,
        plan_id=plan.id,
        provider="sandbox",
        provider_ref=f"sandbox_{uuid.uuid4().hex}",
        amount=plan.price_monthly,
        currency=plan.currency,
        status="pending",
        kind="subscription",
        created_at=utcnow(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def confirm_payment(db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID) -> UserSubscription:
    transaction = db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.id == transaction_id, PaymentTransaction.user_id == user_id
        )
    ).scalar_one_or_none()
    if transaction is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Transaction not found.")
    if transaction.status != "pending":
        raise ApiError(409, "VALIDATION_ERROR", "This transaction was already processed.")

    now = utcnow()
    transaction.status = "succeeded"
    transaction.completed_at = now

    subscription, _ = get_or_create_subscription(db, user_id)
    subscription.plan_id = transaction.plan_id
    subscription.status = "active"
    subscription.cancelled_at = None
    subscription.current_period_start = _period_start(now)
    subscription.current_period_end = _next_month_start(now)
    subscription.updated_at = now
    db.commit()
    db.refresh(subscription)
    return subscription


def cancel_subscription(db: Session, user_id: uuid.UUID) -> UserSubscription:
    subscription, plan = get_or_create_subscription(db, user_id)
    if plan.code == FREE_PLAN_CODE:
        raise ApiError(409, "VALIDATION_ERROR", "The free plan cannot be cancelled.")
    if subscription.status != "active":
        raise ApiError(409, "VALIDATION_ERROR", "This subscription is not active.")
    subscription.status = "cancelled"
    subscription.cancelled_at = utcnow()
    subscription.updated_at = utcnow()
    db.commit()
    db.refresh(subscription)
    return subscription


def history(db: Session, user_id: uuid.UUID) -> list[PaymentTransaction]:
    rows = db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.user_id == user_id)
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
    ).scalars()
    return list(rows)


def usage_data(db: Session, user_id: uuid.UUID) -> UsageData:
    _, plan = get_or_create_subscription(db, user_id)
    meter = _meter(db, user_id)
    db.commit()
    unlimited_free = plan.code == FREE_PLAN_CODE and _free_quotas_disabled()
    return UsageData(
        plan_code=plan.code,
        period_start=meter.period_start.isoformat(),
        ai_calls=meter.ai_calls,
        evaluations=meter.evaluations,
        quota_ai_calls_monthly=None if unlimited_free else plan.quota_ai_calls_monthly,
        quota_evaluations_monthly=None if unlimited_free else plan.quota_evaluations_monthly,
    )
