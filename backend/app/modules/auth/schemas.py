"""Auth request/response schemas. Shapes follow API Specification §3.2;
the OpenAPI contract leaves auth response bodies open (descriptions only)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import RequestMeta


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, json_schema_extra={"writeOnly": True})
    display_name: str | None = Field(default=None, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(json_schema_extra={"writeOnly": True})


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None


class AuthData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


class AuthResponse(BaseModel):
    data: AuthData
    meta: RequestMeta | None = None


class SessionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_label: str | None
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    is_current: bool = False

    @field_validator("ip_address", mode="before")
    @classmethod
    def _stringify_ip(cls, value):
        # psycopg returns INET columns as ipaddress objects, not strings.
        return str(value) if value is not None else None


class SessionsResponse(BaseModel):
    data: list[SessionItem]
    meta: RequestMeta | None = None


class LogoutAllData(BaseModel):
    revoked_sessions: int


class LogoutAllResponse(BaseModel):
    data: LogoutAllData
    meta: RequestMeta | None = None
