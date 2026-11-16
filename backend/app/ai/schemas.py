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


class SentenceCheckIssue(BaseModel):
    """One finding of the whole-sentence LLM grammar scan (ADR-025).

    Offsets are unicode code points RELATIVE to the checked sentence; the
    service validates them against the sentence text before use.
    """

    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=30)
    sub_category: str | None = Field(default=None, max_length=80)
    severity: Severity
    short_explanation: str = Field(min_length=1, max_length=500)
    suggestions: list[str] = Field(min_length=1, max_length=3)
    confidence: float = Field(ge=0.0, le=1.0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    anchor_text: str = Field(min_length=1, max_length=200)


class SentenceCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[SentenceCheckIssue] = Field(default_factory=list, max_length=10)


class GhostProgressResult(BaseModel):
    """Whether a completed sentence fulfills its outline guidance (ADR-025)."""

    model_config = ConfigDict(extra="forbid")

    fulfilled: bool
    reason: str | None = Field(default=None, max_length=500)


class TeachingExamplePair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wrong: str = Field(min_length=1, max_length=300)
    correct: str = Field(min_length=1, max_length=300)
    note: str = Field(min_length=1, max_length=300)


class TeachingKnowledgePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(min_length=1, max_length=2000)
    pattern: str = Field(min_length=1, max_length=200)
    examples: list[TeachingExamplePair] = Field(min_length=2, max_length=3)


class TeachingContentV2(BaseModel):
    """Structured teaching (ADR-026): knowledge point first, then the
    sentence-specific reason. Rendered visually by the client."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    knowledge_point: TeachingKnowledgePoint
    sentence_reason: str = Field(min_length=1, max_length=1000)
    recommended_correction: str = Field(min_length=1, max_length=500)
    personalized_note: str | None = Field(default=None, max_length=1000)


class PolishOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    meaning: str = Field(min_length=1, max_length=500)
    usage: str = Field(min_length=1, max_length=500)
    formality: Literal["formal", "neutral", "informal"]


class PolishFragment(BaseModel):
    """One unnatural fragment with drop-in replacement options (ADR-026).

    Offsets are unicode code points RELATIVE to the checked sentence.
    """

    model_config = ConfigDict(extra="forbid")

    anchor_text: str = Field(min_length=1, max_length=300)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    note: str = Field(min_length=1, max_length=500)
    options: list[PolishOption] = Field(min_length=3, max_length=3)


class PolishSentenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragments: list[PolishFragment] = Field(default_factory=list, max_length=5)


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
    # ADR-029: LLM output tolerance — providers occasionally add stray fields
    # (e.g. title_note); drop them instead of failing the whole call.
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=255)
    # Structure is the AI's choice (IELTS-appropriate), not a fixed template;
    # bounds are sanity caps only.
    sentence_ideas: list[str] = Field(min_length=1, max_length=10)


class OutlineSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=255)
    paragraphs: list[OutlineParagraph] = Field(min_length=1, max_length=8)


class OutlineGenerationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    thesis_statement: str = Field(min_length=1, max_length=1000)
    sections: list[OutlineSection] = Field(min_length=1, max_length=8)
    # ADR-032: clean markdown rendering of the outline for readable display.
    outline_md: str | None = Field(default=None, max_length=20000)


class PlannerChatResult(BaseModel):
    """Conversational planner turn (ADR-024/032): chat reply plus, for
    propose/revise, the ENGLISH model essay, its sentence-aligned CHINESE
    translation (drives ghost hints), and the outline (structured + markdown)."""

    model_config = ConfigDict(extra="ignore")

    reply: str = Field(min_length=1, max_length=1000)
    action: Literal["discuss", "propose", "revise"]
    outline: OutlineGenerationResult | None = None
    model_essay: str | None = Field(default=None, max_length=20000)
    model_essay_zh: str | None = Field(default=None, max_length=20000)


class ModelEssayResult(BaseModel):
    """ADR-032: an English model essay generated from an outline plus its
    sentence-by-sentence Chinese translation (1:1 sentence alignment). Used to
    bootstrap/refresh ghost guidance. Tolerates stray provider fields."""

    model_config = ConfigDict(extra="ignore")

    model_essay: str = Field(min_length=1, max_length=20000)
    model_essay_zh: str = Field(min_length=1, max_length=20000)


class StudySuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=1000)
    task_type: Literal["review", "practice", "writing"]


class StudyPlanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_areas: list[str] = Field(min_length=1, max_length=5)
    suggestions: list[StudySuggestion] = Field(min_length=2, max_length=6)
