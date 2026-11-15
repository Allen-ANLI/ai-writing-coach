"""User profile schemas for GET/PATCH /users/me.

The OpenAPI contract types the PATCH body as an open object; the allowed
fields below mirror the ERD user_profiles columns (preferences has its own
dedicated endpoint in a later slice). Unknown fields are rejected.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta


class ProfileData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None
    native_language: str
    english_level: str | None
    target_exam: str | None
    target_writing_score: Decimal | None
    preferred_english_variant: str | None
    preferences: dict


class MeData(BaseModel):
    id: uuid.UUID
    email: str
    status: str
    email_verified_at: datetime | None
    created_at: datetime
    profile: ProfileData


class MeResponse(BaseModel):
    data: MeData
    meta: RequestMeta | None = None


class PatchMeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=80)
    native_language: str | None = Field(default=None, max_length=20)
    english_level: str | None = Field(default=None, max_length=30)
    target_exam: str | None = Field(default=None, max_length=30)
    target_writing_score: Decimal | None = Field(
        default=None, ge=0, le=9, max_digits=3, decimal_places=1
    )
    preferred_english_variant: str | None = Field(default=None, max_length=20)


class PreferencesData(BaseModel):
    auto_grammar_check: bool = True
    auto_expression_assist: bool = True
    daily_review_goal: int | None = Field(default=None, ge=1, le=100)
    ui_language: Literal["zh", "en"] = "zh"


class PatchPreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_grammar_check: bool | None = None
    auto_expression_assist: bool | None = None
    daily_review_goal: int | None = Field(default=None, ge=1, le=100)
    ui_language: Literal["zh", "en"] | None = None


class PreferencesResponse(BaseModel):
    data: PreferencesData
    meta: RequestMeta | None = None
