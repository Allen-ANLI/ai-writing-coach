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
    # ADR-034: live mode = Word-like instant rule-only check on the current
    # (possibly unsaved) cursor sentence. No revision/text_range-vs-doc gate,
    # no LLM, no persistence; issues are ephemeral display-only.
    live: bool = False
    # ADR-035: whether the checked sentence is complete (terminator typed or
    # paragraph break). Live mode only surfaces non-spelling findings when
    # this is true; spelling stays instant once the word is finalized.
    sentence_complete: bool = False


class SuggestionStub(BaseModel):
    id: uuid.UUID
    display_text: str = "••••"
    answer_revealed: bool = False
    # ADR-034: live (ephemeral) issues set answer_revealed=True and put the
    # deterministic correction in display_text so it shows instantly without a
    # DB reveal. Persisted issues stay masked ("••••", answer_revealed=False)
    # and never carry suggested_text before an explicit reveal.


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
    # ADR-034: true for ephemeral live-check findings (no DB row); the frontend
    # routes hover/accept differently (pre-revealed; accept-after-save).
    live: bool = False


class GrammarCheckData(BaseModel):
    server_revision: int
    client_revision: int
    check_status: Literal["completed", "partial", "live"]
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


class AcceptIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    suggestion_id: uuid.UUID | None = None


class LiveAcceptRequest(BaseModel):
    """ADR-035: accept an ephemeral live finding in one atomic call.

    The server re-derives the deterministic rule hit (no LLM) and only applies
    a replacement that is among its own suggestions — the client merely picks
    an option the server already offered, never supplies free replacement text.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    base_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    rule_id: str = Field(min_length=1, max_length=200)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    anchor_text: str = Field(min_length=1, max_length=2000)
    replacement: str = Field(min_length=1, max_length=2000)


class AcceptIssueData(BaseModel):
    issue_id: uuid.UUID
    suggestion_id: uuid.UUID
    server_revision: int
    applied_text: str
    content_json: dict
    plain_text: str
    word_count: int


class AcceptIssueResponse(BaseModel):
    data: AcceptIssueData
    meta: RequestMeta | None = None


class TeachingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server_revision: int = Field(ge=1)
    client_revision: int = Field(ge=0)
    current_sentence: str = Field(min_length=1, max_length=5000)
    paragraph_context: str | None = Field(default=None, max_length=10000)
    user_current_text: str | None = Field(default=None, max_length=5000)


class TeachingExamplePairData(BaseModel):
    wrong: str
    correct: str
    note: str


class TeachingKnowledgePointData(BaseModel):
    explanation: str
    pattern: str
    examples: list[TeachingExamplePairData]


class TeachingData(BaseModel):
    """ADR-026 structured teaching: knowledge point first, then the
    sentence-specific reason."""

    teaching_id: uuid.UUID
    issue_id: uuid.UUID
    source_server_revision: int
    title: str
    knowledge_point: TeachingKnowledgePointData
    sentence_reason: str
    recommended_correction: str
    personalized_note: str | None


class TeachingResponse(BaseModel):
    data: TeachingData
    meta: RequestMeta | None = None
