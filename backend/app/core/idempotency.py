"""Idempotency-Key deduplication for important write operations (API Spec §2).

Scoped per authenticated user. The first request inserts a placeholder, runs
the operation, then stores the response; repeats with the same key and payload
replay the stored response without re-executing. Same key with a different
payload is rejected (422). A concurrent repeat while the first request is still
in flight gets 429 (retry shortly); placeholders abandoned by a crash are
reclaimed after a short window.

Storage is PostgreSQL so it stays correct across workers; the access point is
isolated here for a future move to shared cache storage if needed.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.infrastructure.database import Base

_STALE_PLACEHOLDER = timedelta(seconds=60)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    method: Mapped[str]
    path: Mapped[str]
    request_hash: Mapped[str]
    response_status: Mapped[int | None]
    response_body: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)


def payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def run_idempotent(
    db: Session,
    user_id: uuid.UUID,
    key: str | None,
    *,
    method: str,
    path: str,
    request_hash: str,
    operation: Callable[[], JSONResponse],
) -> JSONResponse:
    if key is None:
        return operation()

    now = utcnow()
    # RETURNING is the reliable conflict signal here: psycopg reports rowcount
    # -1 for INSERT ... ON CONFLICT DO NOTHING, so a returned row means we own
    # the placeholder and no row means an earlier request already holds the key.
    inserted = db.execute(
        pg_insert(IdempotencyRecord)
        .values(
            user_id=user_id,
            key=key,
            method=method,
            path=path,
            request_hash=request_hash,
            response_status=None,
            response_body=None,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
        .returning(IdempotencyRecord.key)
    )
    owns_placeholder = inserted.scalar_one_or_none() is not None
    db.commit()

    if not owns_placeholder:
        record = db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id, IdempotencyRecord.key == key
            )
        ).scalar_one()
        if record.request_hash != request_hash:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Idempotency-Key was already used with a different payload.",
            )
        if record.response_status is None:
            if record.created_at < now - _STALE_PLACEHOLDER:
                db.execute(
                    delete(IdempotencyRecord).where(
                        IdempotencyRecord.user_id == user_id, IdempotencyRecord.key == key
                    )
                )
                db.commit()
                return run_idempotent(
                    db,
                    user_id,
                    key,
                    method=method,
                    path=path,
                    request_hash=request_hash,
                    operation=operation,
                )
            raise ApiError(
                429,
                "RATE_LIMIT_EXCEEDED",
                "A request with this Idempotency-Key is already in progress; retry shortly.",
            )
        return JSONResponse(status_code=record.response_status, content=record.response_body)

    try:
        response = operation()
    except Exception:
        db.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id, IdempotencyRecord.key == key
            )
        )
        db.commit()
        raise

    record = db.get(IdempotencyRecord, (user_id, key))
    record.response_status = response.status_code
    record.response_body = json.loads(response.body)
    db.commit()
    return response
