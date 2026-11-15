"""Expression API schemas (API Spec §8–9; contract leaves bodies open)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta

# The contract/ERD field name is "register" (linguistic register), which
# shadows a pydantic BaseModel attribute and corrupts JSON-schema generation.
# Attributes are named register_value with validation/serialization aliases so
# the wire format stays exactly "register".

ExpressionStatus = Literal["collected", "learning", "reviewing", "mastered", "archived"]


class CreateExpressionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    english_text: str = Field(min_length=1, max_length=2000)
    chinese_meaning: str | None = Field(default=None, max_length=2000)
    original_text: str | None = Field(default=None, max_length=2000)
    learning_value_reason: str | None = Field(default=None, max_length=2000)
    usage_context: str | None = Field(default=None, max_length=2000)
    topic: str | None = Field(default=None, max_length=80)
    register_value: str | None = Field(
        default=None, max_length=30, validation_alias="register", serialization_alias="register"
    )
    grammar_pattern: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source_type: Literal["translation", "correction", "suggestion", "essay", "manual"] = "manual"
    essay_id: uuid.UUID | None = None
    source_context: str | None = Field(default=None, max_length=5000)


class PatchExpressionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    english_text: str | None = Field(default=None, min_length=1, max_length=2000)
    chinese_meaning: str | None = Field(default=None, max_length=2000)
    usage_context: str | None = Field(default=None, max_length=2000)
    topic: str | None = Field(default=None, max_length=80)
    register_value: str | None = Field(
        default=None, max_length=30, validation_alias="register", serialization_alias="register"
    )
    grammar_pattern: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=20)
    status: ExpressionStatus | None = None


class ExpressionData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    english_text: str
    chinese_meaning: str | None
    original_text: str | None
    learning_value_reason: str | None
    usage_context: str | None
    topic: str | None
    register_value: str | None = Field(
        default=None, validation_alias="register", serialization_alias="register"
    )
    grammar_pattern: str | None
    tags: list[str]
    status: str
    created_at: datetime
    updated_at: datetime


class ExpressionResponse(BaseModel):
    data: ExpressionData
    meta: RequestMeta | None = None


class ExpressionListData(BaseModel):
    items: list[ExpressionData]
    next_cursor: str | None
    limit: int


class ExpressionListResponse(BaseModel):
    data: ExpressionListData
    meta: RequestMeta | None = None


class PolishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    server_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    selected_text: str = Field(min_length=1, max_length=1000)
    sentence: str = Field(min_length=1, max_length=5000)
    paragraph_context: str | None = Field(default=None, max_length=10000)
    max_suggestions: int = Field(default=3, ge=1, le=6)


class TranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    server_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    chinese_text: str = Field(min_length=1, max_length=1000)
    sentence_context: str = Field(min_length=1, max_length=5000)
    paragraph_context: str | None = Field(default=None, max_length=10000)
    exclude: list[str] = Field(default_factory=list, max_length=30)


class SuggestionItemData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    english_text: str
    chinese_meaning: str | None
    usage_note: str | None
    register_value: str | None = Field(
        default=None, validation_alias="register", serialization_alias="register"
    )
    source: str
    expression_id: uuid.UUID | None
    previously_learned: bool
    start_offset: int | None = None
    end_offset: int | None = None
    status: str


class SuggestionData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    essay_id: uuid.UUID
    kind: str
    selected_text: str
    server_revision: int
    status: str
    created_at: datetime
    items: list[SuggestionItemData]


class SuggestionResponse(BaseModel):
    data: SuggestionData
    meta: RequestMeta | None = None


class SuggestionListResponse(BaseModel):
    data: dict
    meta: RequestMeta | None = None


class PolishSentenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    server_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    sentence: str = Field(min_length=1, max_length=5000)
    sentence_range: dict
    paragraph_context: str | None = Field(default=None, max_length=10000)
    fragment_anchor: str | None = Field(default=None, max_length=300)
    exclude: list[str] = Field(default_factory=list, max_length=30)


class PolishSentenceFragmentData(BaseModel):
    suggestion_id: uuid.UUID
    anchor_text: str
    start_offset: int
    end_offset: int
    note: str
    items: list[SuggestionItemData]


class PolishSentenceResponse(BaseModel):
    data: dict
    meta: RequestMeta | None = None


class AcceptSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    base_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    content_json: dict
    plain_text: str | None = None
    word_count: int | None = Field(default=None, ge=0)
    modified_range: dict


class AcceptSuggestionData(BaseModel):
    suggestion_id: uuid.UUID
    item_id: uuid.UUID
    server_revision: int
    content_json: dict
    plain_text: str
    word_count: int


class AcceptSuggestionResponse(BaseModel):
    data: AcceptSuggestionData
    meta: RequestMeta | None = None
