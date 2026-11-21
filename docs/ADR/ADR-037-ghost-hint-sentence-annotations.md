# ADR-037: 幽灵提示逐句“表达 · 句式”注释（生成时预提取）

**Status:** Accepted (2026-11-21, user directive — 方案 A)
**Related:** ADR-025/031/032/033, PRD FR-10.4, contract 1.15.0, migration 0022.

## Context

Ghost hints show the Chinese model-essay sentence the learner should translate
next. The user wants each hint to ALSO surface the **expressions (表达) and
sentence pattern (句式)** that the sentence uses. The material already exists:
planner chat / model-essay generation produce the ENGLISH model essay
(`model_essay`) 1:1 sentence-aligned with the Chinese hints (`model_essay_zh`,
ADR-032) — the Nth English sentence is the source for the Nth hint.

Four options were presented (A: pre-extract at generation; B: on-demand
extract + cache per hint; C: deterministic rule/KB extraction; D: hybrid).
The user chose **A**: extract once when the essay is generated, display
instantly at hint time with zero LLM cost/latency.

## Decision

### Generation-time extraction (shared spec, new prompt versions)

- `_SENTENCE_ANNOTATION_SPEC` (registry constant) appended to
  `planner_chat` **v8** and `model_essay_generate` **v4** (v7/v3 immutable):
  `sentence_annotations` — EXACTLY one annotation per `model_essay` sentence,
  same order (1:1, never merge/split). Each annotation:
  - `expressions`: 2–4 learnable items that are **VERBATIM substrings of that
    English sentence** (collocations/phrases), each with `text`, `meaning`
    (Chinese), `usage` (Chinese);
  - `pattern`: the sentence's 句式 — `label` (short Chinese name), `skeleton`
    (structure with placeholders), `explanation` (one Chinese sentence).
- `SentenceAnnotation` / `SentenceExpressionAnnotation` /
  `SentencePatternAnnotation` AI schemas (`extra="ignore"` tolerance);
  `sentence_annotations` is OPTIONAL on `PlannerChatResult` / `ModelEssayResult`
  so older prompt versions stay valid.

### Storage, validation, lifecycle

- Migration 0022: `writing_outlines.model_essay_annotations` JSONB nullable.
- `validate_annotations` (outlines service): store only when the annotation
  count equals the English sentence count AND every annotation keeps ≥1
  verbatim-grounded expression (non-verbatim expressions are dropped);
  misaligned/ungrounded output degrades to `None` — never blocks generation.
- Annotations share the essay's lifecycle: set in `_create_draft` (planner)
  and `ensure_model_essay` (confirmation bootstrap / model-essay endpoint);
  cleared together with `model_essay`/`model_essay_zh`/`outline_md` on every
  outline edit path (patch outline, node create/patch/delete).
- `OutlineData.model_essay_annotations` served in all outline responses.

### Display (guidance only)

- Ghost widget gains a 表达·句式 button (`ghost-insight-open`); clicking emits
  `awc-ghost:insight` with the hint index + anchor rect. The React layer opens
  `GhostInsightCard`: expression chips (text + meaning + usage; click → add to
  knowledge base via `createExpression` with `source_type="essay"` and the
  English sentence as source context) and the pattern block (label + skeleton
  + explanation). Esc/✕ closes; the card auto-disappears when the hint advances
  or the plan changes (render-time guard, no effect reset).
- Zero LLM calls and zero quota at hint time (annotations are pre-extracted).
- Invariants preserved: annotations are reference guidance — never written
  into the essay body, never counted, never auto-inserted; the widget stays
  outside the persisted document.
- Mock provider returns deterministic annotations 1:1 with the mock essay
  (expressions verbatim), so E2E exercises the full flow.

## Consequences

- Hint-time display is instant and free; cost is a one-time +30–50% output
  tokens at essay generation (larger structured output; schema tolerance +
  validation degrade gracefully on provider drift).
- Legacy outlines have `model_essay_annotations = null` → the button still
  renders but opening is a no-op until the essay is regenerated (confirmation
  bootstrap or the panel's 生成范文指引 button).
- Contract 1.15.0 (additive response field; no new operations, 107 ops).
- Tests: 9 backend tests (validation unit ×4, grounded propose + v8 usage,
  confirm/get carry, draft-edit expiry, v4 regeneration, misaligned degrade);
  E2E insight-card flow (display, KB add, auto-close on advance); existing
  planner/model-essay version assertions updated v7→v8 / v3→v4.