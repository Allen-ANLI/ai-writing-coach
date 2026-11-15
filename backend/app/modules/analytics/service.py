"""User-scoped AI usage analytics (API Spec §16, SD §12.4).

Only the authenticated user's own logs are aggregated; admin-wide statistics
would require a separate permission (not implemented).
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.modules.analytics.models import AiUsageLog
from app.modules.analytics.schemas import FeatureUsage, UsageTotals, UsageTrendPoint
from app.modules.users.models import User

TREND_DAYS = 14


def usage_totals(db: Session, user: User) -> UsageTotals:
    row = db.execute(
        select(
            func.count(AiUsageLog.id),
            func.count(AiUsageLog.id).filter(AiUsageLog.status == "success"),
            func.count(AiUsageLog.id).filter(AiUsageLog.status != "success"),
            func.coalesce(func.sum(AiUsageLog.input_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.output_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.estimated_cost), 0),
        ).where(AiUsageLog.user_id == user.id)
    ).one()
    return UsageTotals(
        total_calls=row[0],
        success_calls=row[1],
        error_calls=row[2],
        input_tokens=row[3],
        output_tokens=row[4],
        estimated_cost=float(row[5]),
    )


def usage_by_feature(db: Session, user: User) -> list[FeatureUsage]:
    rows = db.execute(
        select(
            AiUsageLog.feature,
            func.count(AiUsageLog.id),
            func.coalesce(func.sum(AiUsageLog.input_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.output_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.estimated_cost), 0),
        )
        .where(AiUsageLog.user_id == user.id)
        .group_by(AiUsageLog.feature)
        .order_by(func.count(AiUsageLog.id).desc())
    ).all()
    return [
        FeatureUsage(
            feature=row[0],
            calls=row[1],
            input_tokens=row[2],
            output_tokens=row[3],
            estimated_cost=float(row[4]),
        )
        for row in rows
    ]


def usage_trends(db: Session, user: User) -> list[UsageTrendPoint]:
    today = utcnow().date()
    start = today - timedelta(days=TREND_DAYS - 1)
    day = func.date(AiUsageLog.created_at)
    rows = db.execute(
        select(
            day,
            func.count(AiUsageLog.id),
            func.coalesce(func.sum(AiUsageLog.estimated_cost), 0),
        )
        .where(AiUsageLog.user_id == user.id, day >= start)
        .group_by(day)
    ).all()
    by_day = {row[0]: (row[1], float(row[2])) for row in rows}
    points: list[UsageTrendPoint] = []
    for offset in range(TREND_DAYS):
        current = start + timedelta(days=offset)
        calls, cost = by_day.get(current, (0, 0.0))
        points.append(UsageTrendPoint(date=current, calls=calls, estimated_cost=cost))
    return points
