"""Structured LLM output schemas (SD §7, PRD §7.2). Every model output is
validated against these before it can influence user data."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["high", "medium", "low"]


class DeepCheckIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool
    category: str = Field(min_length=1, max_length=30)
    sub_category: str | None = Field(default=None, max_length=80)
    severity: Severity
    short_explanation: str = Field(min_length=1, max_length=500)
    suggestions: list[str] = Field(min_length=1, max_length=3)
    confidence: float = Field(ge=0.0, le=1.0)


class DeepCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[DeepCheckIssue] = Field(default_factory=list, max_length=10)


class TeachingContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    why_wrong: str = Field(min_length=1, max_length=2000)
    grammar_rule: str = Field(min_length=1, max_length=2000)
    recommended_correction: str = Field(min_length=1, max_length=500)
    personalized_note: str | None = Field(default=None, max_length=1000)
    examples: list[str] = Field(min_length=2, max_length=3)
    practice: str | None = Field(default=None, max_length=1000)


class PolishSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    meaning: str = Field(min_length=1, max_length=500)
    usage: str = Field(min_length=1, max_length=500)
    formality: str = Field(min_length=1, max_length=30)


class PolishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[PolishSuggestion] = Field(min_length=1, max_length=6)


class TranslationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    english_text: str = Field(min_length=1, max_length=500)
    chinese_meaning: str = Field(min_length=1, max_length=500)
    usage_note: str = Field(min_length=1, max_length=500)
    formality: str = Field(min_length=1, max_length=30)


class TranslationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[TranslationCandidate] = Field(min_length=2, max_length=4)


class ValidationJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["correct", "incorrect", "needs_review"]
    reason: str = Field(min_length=1, max_length=1000)


class ExtractedExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    english_text: str = Field(min_length=1, max_length=500)
    chinese_meaning: str = Field(min_length=1, max_length=500)
    original_text: str | None = Field(default=None, max_length=500)
    learning_value_reason: str = Field(min_length=1, max_length=1000)
    usage_context: str | None = Field(default=None, max_length=500)
    topic: str | None = Field(default=None, max_length=80)
    grammar_pattern: str | None = Field(default=None, max_length=500)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ExtractedExpression] = Field(default_factory=list, max_length=10)


class ReviewJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_correct: bool
    score: float = Field(ge=0.0, le=5.0)
    feedback: str | None = Field(default=None, max_length=1000)


class PracticeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chinese_prompt: str = Field(min_length=1, max_length=500)
    hint: str | None = Field(default=None, max_length=500)


class PracticeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PracticeItem] = Field(min_length=1, max_length=10)


class CriterionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    band: float = Field(ge=0.0, le=9.0)
    feedback: str = Field(min_length=1, max_length=1000)


class IeltsTask1EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_achievement: CriterionScore
    coherence_cohesion: CriterionScore
    lexical_resource: CriterionScore
    grammatical_range_accuracy: CriterionScore
    overall_feedback: str = Field(min_length=1, max_length=2000)
    strengths: list[str] = Field(min_length=1, max_length=3)
    improvements: list[str] = Field(min_length=1, max_length=3)


class IeltsTask2EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_response: CriterionScore
    coherence_cohesion: CriterionScore
    lexical_resource: CriterionScore
    grammatical_range_accuracy: CriterionScore
    overall_feedback: str = Field(min_length=1, max_length=2000)
    strengths: list[str] = Field(min_length=1, max_length=3)
    improvements: list[str] = Field(min_length=1, max_length=3)


class GeneralEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: CriterionScore
    organization: CriterionScore
    language: CriterionScore
    overall_feedback: str = Field(min_length=1, max_length=2000)
    strengths: list[str] = Field(min_length=1, max_length=3)
    improvements: list[str] = Field(min_length=1, max_length=3)


class RewriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rewritten_text: str = Field(min_length=1, max_length=20000)
    change_summary: str = Field(min_length=1, max_length=2000)


class OutlineParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    sentence_ideas: list[str] = Field(min_length=1, max_length=4)


class OutlineSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    paragraphs: list[OutlineParagraph] = Field(min_length=1, max_length=4)


class OutlineGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis_statement: str = Field(min_length=1, max_length=1000)
    sections: list[OutlineSection] = Field(min_length=2, max_length=5)


class PlannerChatResult(BaseModel):
    """Conversational planner turn (ADR-024): chat reply plus an optional
    proposed/revised outline. outline is only honored for propose/revise."""

    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1, max_length=1000)
    action: Literal["discuss", "propose", "revise"]
    outline: OutlineGenerationResult | None = None


class StudySuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=1000)
    task_type: Literal["review", "practice", "writing"]


class StudyPlanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_areas: list[str] = Field(min_length=1, max_length=5)
    suggestions: list[StudySuggestion] = Field(min_length=2, max_length=6)
