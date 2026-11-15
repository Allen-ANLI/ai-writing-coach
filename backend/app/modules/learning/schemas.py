"""Learning API schemas (API Spec §10–11)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import RequestMeta


class ReviewPrompt(BaseModel):
    expression_id: uuid.UUID
    chinese_meaning: str | None
    topic: str | None
    usage_context: str | None
    status: str
    next_review_at: datetime | None
    review_count: int


class DueReviewsData(BaseModel):
    items: list[ReviewPrompt]
    due_count: int


class DueReviewsResponse(BaseModel):
    data: DueReviewsData
    meta: RequestMeta | None = None


class SubmitReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression_id: uuid.UUID
    user_answer: str = Field(min_length=1, max_length=2000)
    exercise_mode: str = "translation"


class ReviewResultData(BaseModel):
    expression_id: uuid.UUID
    is_correct: bool
    score: Decimal
    feedback: str | None
    reference_expression: str
    status: str
    interval_days: Decimal
    next_review_at: datetime | None
    streak_count: int


class ReviewResultResponse(BaseModel):
    data: ReviewResultData
    meta: RequestMeta | None = None


class ProgressData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expression_id: uuid.UUID
    status: str
    correct_count: int
    incorrect_count: int
    review_count: int
    streak_count: int
    interval_days: Decimal
    ease_factor: Decimal | None
    last_reviewed_at: datetime | None
    next_review_at: datetime | None


class ProgressResponse(BaseModel):
    data: ProgressData
    meta: RequestMeta | None = None


class LearningSummaryData(BaseModel):
    total_expressions: int
    by_status: dict[str, int]
    due_now: int
    reviewed_today: int
    mastered: int
    total_reviews: int


class LearningSummaryResponse(BaseModel):
    data: LearningSummaryData
    meta: RequestMeta | None = None


class WeaknessData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    sub_category: str
    total_occurrences: int
    recent_occurrences: int
    last_occurred_at: datetime | None
    trend: str | None


class WeaknessListData(BaseModel):
    items: list[WeaknessData]


class WeaknessListResponse(BaseModel):
    data: WeaknessListData
    meta: RequestMeta | None = None


class WeaknessExample(BaseModel):
    essay_id: uuid.UUID
    anchor_text: str
    short_explanation: str | None
    created_at: datetime


class WeaknessDetailData(BaseModel):
    category: str
    total_occurrences: int
    recent_occurrences: int
    trend: str | None
    examples: list[WeaknessExample]


class WeaknessDetailResponse(BaseModel):
    data: WeaknessDetailData
    meta: RequestMeta | None = None


class TrendPoint(BaseModel):
    period_start: datetime
    issues: int
    words_written: int
    errors_per_1000_words: Decimal | None


class WeaknessTrendsData(BaseModel):
    category: str | None
    points: list[TrendPoint]
    methodology: str


class WeaknessTrendsResponse(BaseModel):
    data: WeaknessTrendsData
    meta: RequestMeta | None = None


class PracticeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=50)
    count: int = Field(default=3, ge=1, le=10)


class PracticeItem(BaseModel):
    chinese_prompt: str
    hint: str | None


class PracticeData(BaseModel):
    category: str
    items: list[PracticeItem]


class PracticeResponse(BaseModel):
    data: PracticeData
    meta: RequestMeta | None = None
