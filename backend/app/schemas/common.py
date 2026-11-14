"""Shared response envelope pieces (API Spec §2)."""

from uuid import uuid4

from pydantic import BaseModel


def new_request_id() -> str:
    return str(uuid4())


class RequestMeta(BaseModel):
    request_id: str | None = None


class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str | None = None


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorInfo
    meta: RequestMeta | None = None
