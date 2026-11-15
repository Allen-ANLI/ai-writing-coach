# ADR-016 — Finalized Writing Editor UX

**Date:** 2026-11-15
**Status:** Accepted (user decision, supersedes conflicting earlier assumptions)
**Supersedes parts of:** PRD V1.1 §4.2 layout sketch, Slice 3 initial grammar UI

## Context

The user finalized the writing-editor interaction model after reviewing the
first grammar implementation. These decisions are newer than the PRD sketch
and the initial Slice 3 UI and override them where they conflict.

## Decision

1. **Essay question separation.** The question/prompt is displayed in a
   separate, clearly distinguishable, non-editable section. It is never mixed
   into the editable essay document. Data: `essays.question_prompt` (nullable
   text snapshot; `question_id` remains the future IELTS-bank link).
2. **Left outline.** Collapsible hierarchical TEXT list (never a chart or
   diagram): essay sections (headings) → paragraphs → sentence-level ideas.
   Expand/collapse per item; synchronized with the document; click navigates.
3. **Automatic grammar checking.** No manual grammar-check button and no
   numbered errors. Checks trigger on sentence completion (punctuation or
   paragraph break) with debounce and request cancellation; incomplete input
   is never checked prematurely. Sentence detection handles abbreviations,
   decimals, initials, quoted sentences, IME composition and pasted content.
   Rule-first remains: LanguageTool + deterministic rules before any LLM.
4. **Hover feedback.** The incorrect text stays underlined (category colors).
   The short explanation appears when hovering the error, in a floating,
   slightly transparent card above content, without obstructing editing.
5. **Blurred answer.** The correction is blurred initially. There is NO
   reveal button: clicking the blurred correction itself reveals it. After
   reveal, the card shows "Press Tab to replace the original text." Tab
   accepts and replaces ONLY while the correction interaction is active
   (pinned); otherwise Tab keeps normal editor behavior. Acceptance applies
   the server-stored suggestion atomically (POST .../issues/{id}/accept).
6. **Teaching.** Only a small teaching icon next to the feedback opens the
   contextual floating teaching card (actual sentence + paragraph context).
   No permanent grammar panel.
7. **Toolbar.** No grammar-check icon; no Submit Essay button during writing.
   Writing is continuous with autosave. IELTS evaluation, overall assessment,
   improvement recommendations and rewrite levels are post-writing actions
   (Slice 7), not a mandatory submission step. The session submit API remains
   for the evaluation flow.

## Preserved core decisions

Exactly two writing modes (assisted/independent, backend-enforced);
rule-first / LLM-on-demand; Original snapshot preservation; autosave +
revision concurrency; contextual teaching; Chinese-to-English assistance;
personal knowledge base; previously-learned recommendations; repeated
weakness detection; user-controlled acceptance.

## Consequences

- Slice 3 hint widgets replaced by hover card + pinned correction state.
- New contract operation `POST /essays/{essay_id}/issues/{issue_id}/accept`
  (OpenAPI 1.2.0, additive) and `essays.question_prompt`.
- E2E rewritten to the finalized interactions (38 tests passing).
- Evaluation/rewrite UI lands in Slice 7 as post-writing actions.
