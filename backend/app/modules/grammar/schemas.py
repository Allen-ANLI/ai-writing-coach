"""Grammar API schemas (API Spec §6–7, contract GrammarIssue / TeachingResponse).

Unrevelaed suggestions are exposed ONLY as {id, display_text:"••••",
answer_revealed:false}; suggested_text never appears before an explicit reveal.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta

OffsetUnit = Literal["unicode_codepoint"]


class TextRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=1)
    offset_unit: OffsetUnit = "unicode_codepoint"


class GrammarCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    server_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=20000)
    text_range: TextRange
    context: dict | None = None


class SuggestionStub(BaseModel):
    id: uuid.UUID
    display_text: str = "••••"
    answer_revealed: bool = False


class IssueData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    sub_category: str | None
    source: str
    rule_id: str | None
    severity: str
    source_server_revision: int
    essay_version_id: uuid.UUID | None
    start_offset: int
    end_offset: int
    offset_unit: OffsetUnit = "unicode_codepoint"
    anchor_text: str
    short_explanation: str | None
    status: str
    suggestions: list[SuggestionStub]


class GrammarCheckData(BaseModel):
    server_revision: int
    client_revision: int
    check_status: Literal["completed", "partial"]
    issues: list[IssueData]


class GrammarCheckResponse(BaseModel):
    data: GrammarCheckData
    meta: RequestMeta | None = None


class IssueListData(BaseModel):
    items: list[IssueData]


class IssueListResponse(BaseModel):
    data: IssueListData
    meta: RequestMeta | None = None


class IssueResponse(BaseModel):
    data: IssueData
    meta: RequestMeta | None = None


class IssueValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: uuid.UUID
    base_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    content_json: dict
    plain_text: str | None = None
    word_count: int | None = Field(default=None, ge=0)
    modified_range: TextRange


class IssueValidationData(BaseModel):
    issue_id: uuid.UUID
    validation_status: Literal["correct", "incorrect", "needs_review"]
    is_resolved: bool
    server_revision: int


class IssueValidationResponse(BaseModel):
    data: IssueValidationData
    meta: RequestMeta | None = None


class RevealedSuggestion(BaseModel):
    id: uuid.UUID
    suggested_text: str
    explanation: str | None
    is_recommended: bool


class RevealData(BaseModel):
    issue_id: uuid.UUID
    suggestions: list[RevealedSuggestion]


class RevealResponse(BaseModel):
    data: RevealData
    meta: RequestMeta | None = None


class IgnoreIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ignored"]


class TeachingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    current_sentence: str = Field(min_length=1, max_length=5000)
    paragraph_context: str | None = Field(default=None, max_length=10000)
    user_current_text: str | None = Field(default=None, max_length=5000)


class TeachingData(BaseModel):
    teaching_id: uuid.UUID
    issue_id: uuid.UUID
    source_server_revision: int
    title: str
    why_wrong: str
    grammar_rule: str
    recommended_correction: str
    personalized_note: str | None


class TeachingResponse(BaseModel):
    data: TeachingData
    meta: RequestMeta | None = None
