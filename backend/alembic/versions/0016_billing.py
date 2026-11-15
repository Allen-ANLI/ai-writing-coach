"""billing: subscription_plans, user_subscriptions, usage_meters, payment_transactions

Stage 2 Slice 10 (reconciliation R8). Additive; does not modify 0001-0015.

Notes:
- Payment provider is SANDBOX ONLY until real activation is explicitly
  approved (Directive §6/§10, ADR-021). provider is constrained to 'sandbox'.
- Plan seed is product configuration (free/pro/ultimate); quotas are monthly
  per calendar period. NULL quota means unlimited.
- usage_meters counts actual LLM calls (metered at record_usage) and queued
  evaluations; pure rule checks never consume quota (SD §12.4).
- One subscription row per user (UNIQUE user_id); free tier is materialized
  lazily on first billing/quota access.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-15

"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import context, op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

PLANS = [
    {
        "code": "free",
        "name": "Free",
        "price_monthly": "0.00",
        "quota_ai_calls_monthly": 100,
        "quota_evaluations_monthly": 10,
        "features": {
            "grammar_check": True,
            "expression_assist": True,
            "evaluations": True,
            "rewrites": True,
            "outlines": True,
            "workflows": True,
        },
    },
    {
        "code": "pro",
        "name": "Pro",
        "price_monthly": "19.00",
        "quota_ai_calls_monthly": 1000,
        "quota_evaluations_monthly": 100,
        "features": {
            "grammar_check": True,
            "expression_assist": True,
            "evaluations": True,
            "rewrites": True,
            "outlines": True,
            "workflows": True,
            "priority_support": True,
        },
    },
    {
        "code": "ultimate",
        "name": "Ultimate",
        "price_monthly": "39.00",
        "quota_ai_calls_monthly": None,
        "quota_evaluations_monthly": None,
        "features": {
            "grammar_check": True,
            "expression_assist": True,
            "evaluations": True,
            "rewrites": True,
            "outlines": True,
            "workflows": True,
            "priority_support": True,
            "early_features": True,
        },
    },
]


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("price_monthly", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("features", JSONB(), nullable=False),
        sa.Column("quota_ai_calls_monthly", sa.Integer(), nullable=True),
        sa.Column("quota_evaluations_monthly", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price_monthly >= 0", name="ck_subscription_plans_price"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_subscription_plans_code"),
    )

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled', 'expired', 'past_due')",
            name="ck_user_subscriptions_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_subscriptions_user"),
    )

    op.create_table(
        "usage_meters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("ai_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("evaluations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ai_calls >= 0", name="ck_usage_meters_ai_calls"),
        sa.CheckConstraint("evaluations >= 0", name="ck_usage_meters_evaluations"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "period_start", name="uq_usage_meters_user_period"),
    )

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), server_default="sandbox", nullable=False),
        sa.Column("provider_ref", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("kind", sa.String(length=30), server_default="subscription", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("provider IN ('sandbox')", name="ck_payment_transactions_provider"),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'refunded')",
            name="ck_payment_transactions_status",
        ),
        sa.CheckConstraint(
            "kind IN ('subscription', 'refund')", name="ck_payment_transactions_kind"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payment_transactions_user_created",
        "payment_transactions",
        ["user_id", sa.text("created_at DESC")],
    )

    # Plan seed needs a live connection (JSONB literals cannot render in
    # offline --sql mode); offline emits DDL only, same as migration 0012.
    if context.is_offline_mode():
        return
    plans_table = sa.table(
        "subscription_plans",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("price_monthly", sa.Numeric()),
        sa.column("currency", sa.String()),
        sa.column("features", JSONB()),
        sa.column("quota_ai_calls_monthly", sa.Integer()),
        sa.column("quota_evaluations_monthly", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        plans_table,
        [
            {
                "id": uuid.uuid5(_NAMESPACE, f"ai-writing-coach:plan:{plan['code']}"),
                "code": plan["code"],
                "name": plan["name"],
                "price_monthly": plan["price_monthly"],
                "currency": "USD",
                "features": plan["features"],
                "quota_ai_calls_monthly": plan["quota_ai_calls_monthly"],
                "quota_evaluations_monthly": plan["quota_evaluations_monthly"],
                "is_active": True,
                "created_at": datetime.now(UTC),
            }
            for plan in PLANS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_user_created", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_table("usage_meters")
    op.drop_table("user_subscriptions")
    op.drop_table("subscription_plans")
