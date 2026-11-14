"""Health and error envelopes mirroring contracts/openapi.yaml (HealthResponse,
ErrorResponse). Verified by tests/test_contract.py."""

from typing import Literal

from pydantic import BaseModel


class HealthData(BaseModel):
    status: Literal["ok"]
    database: Literal["connected"]


class RequestMeta(BaseModel):
    request_id: str | None = None


class HealthResponse(BaseModel):
    data: HealthData
    meta: RequestMeta | None = None


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
