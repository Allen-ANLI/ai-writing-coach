"""Billing routes (thin). Sandbox payments only (ADR-021)."""

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.idempotency import payload_hash, run_idempotent
from app.infrastructure.database import get_db
from app.modules.billing import service
from app.modules.billing.models import SubscriptionPlan
from app.modules.billing.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    ConfirmRequest,
    HistoryListResponse,
    PlanListResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


def _subscription_response(db: Session, user: User) -> SubscriptionResponse:
    return SubscriptionResponse.model_validate(
        {"data": service.subscription_data(db, user.id), "meta": {"request_id": new_request_id()}}
    )


@router.get("/billing/plans", response_model=PlanListResponse)
def list_plans(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanListResponse:
    items = service.list_plans(db)
    return PlanListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/billing/subscription", response_model=SubscriptionResponse)
def get_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    return _subscription_response(db, user)


@router.post("/billing/checkout", status_code=201)
def checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> JSONResponse:
    def operation() -> JSONResponse:
        transaction = service.checkout(db, user.id, payload.plan_code)
        plan = db.get(SubscriptionPlan, transaction.plan_id)
        body = CheckoutResponse.model_validate(
            {
                "data": {
                    "transaction_id": transaction.id,
                    "plan_code": plan.code,
                    "amount": transaction.amount,
                    "currency": transaction.currency,
                    "provider": transaction.provider,
                    "status": transaction.status,
                },
                "meta": {"request_id": new_request_id()},
            }
        )
        return JSONResponse(status_code=201, content=body.model_dump(mode="json"))

    return run_idempotent(
        db,
        user.id,
        idempotency_key,
        method="POST",
        path="/billing/checkout",
        request_hash=payload_hash(payload.model_dump_json()),
        operation=operation,
    )


@router.post("/billing/confirm")
def confirm(
    payload: ConfirmRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> JSONResponse:
    def operation() -> JSONResponse:
        service.confirm_payment(db, user.id, payload.transaction_id)
        body = _subscription_response(db, user)
        return JSONResponse(status_code=200, content=body.model_dump(mode="json"))

    return run_idempotent(
        db,
        user.id,
        idempotency_key,
        method="POST",
        path="/billing/confirm",
        request_hash=payload_hash(payload.model_dump_json()),
        operation=operation,
    )


@router.post("/billing/cancel", response_model=SubscriptionResponse)
def cancel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    service.cancel_subscription(db, user.id)
    return _subscription_response(db, user)


@router.get("/billing/history", response_model=HistoryListResponse)
def history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryListResponse:
    items = service.history(db, user.id)
    return HistoryListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/billing/usage", response_model=UsageResponse)
def usage(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageResponse:
    return UsageResponse.model_validate(
        {"data": service.usage_data(db, user.id), "meta": {"request_id": new_request_id()}}
    )
