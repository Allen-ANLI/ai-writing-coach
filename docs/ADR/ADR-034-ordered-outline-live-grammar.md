# ADR-034: 大纲序号化 + Word 式即时语法纠错

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-024/025/027/028/029/033, PRD FR-02, contract 1.12.0.

## Context

1. **Outline numbering**: the hierarchical outline embedded numbers inside the
   bold labels (`- **原因1：生活节奏快**`). The user wants the number to be a
   real ordered-list marker (`1.`) instead of part of the label text.
2. **Grammar latency**: grammar checking felt nothing like Word. Three delays
   compounded: (a) the check was gated on autosave (the backend validates
   `text_range` verbatim against the saved working document at the current
   `server_revision`); (b) the frontend only checked COMPLETE sentences (a
   sentence terminator had to be typed); (c) LanguageTool results were bundled
   with the LLM deep-check + whole-sentence scan in one response, so even
   deterministic spelling/agreement errors waited 1–3s for the LLM. Polish is
   also sentence-completion triggered, so the two felt coupled.
3. The user asked whether the short error explanation comes from the LLM.
   **Answer**: deterministic rule errors (spelling, agreement, articles,
   punctuation…) use preset Chinese templates (`_RULE_EXPLANATIONS_ZH`) or the
   LanguageTool message with a Chinese category prefix — **not the LLM**, so
   they are available instantly. Only LLM-detected errors (uncertain fragments
   confirmed by the deep checker, or hidden errors found by the sentence scan)
   have LLM-generated explanations. This is exactly why a Word-like instant
   rule-only path is feasible.

User decisions (ask_user_question): grammar architecture = **Live instant
display + deep analysis after save**; check scope = **the cursor sentence /
paragraph** (including incomplete input).

## Decision

### Outline ordered-list numbering
- `planner_chat v7` / `outline_generate v6` (immutable new versions): `outline_md`
  uses ORDERED-LIST markers — `## ` section, `### ` paragraph,
  `1. **短概括**：详解。例如：例子。` per idea (the `1.`, `2.` marker provides the
  ordering; the bold label no longer embeds a number), `   1. ` nested ordered
  sub-points. Structured `sentence_idea` labels drop the embedded "原因1" number.
- Frontend `outline-markdown.tsx`: `parseOutlineMarkdown` parses ordered markers
  (`/^\d+\.\s/`) into `{type:"ordered", depth, number, text}` and renders the
  numeric marker with nested indentation. `- `/`* ` bullets remain supported for
  older outlines (backward compatible). Mock `outline_md` updated to ordered.

### Word-like live grammar (Live LT-only + deep on save)
- **Backend** `grammar-check` gains an optional `live` flag. When `live=true`:
  ownership/session/mode checks only; **skip** the saved-revision and
  text_range-vs-doc gates (validate offsets within the submitted text instead);
  run the rule engine and keep **deterministic** hits only; **no LLM, no billing,
  no persistence**. Returns ephemeral issues with stable synthetic ids
  (`uuid5` over essay+rule+span+anchor), absolute offsets
  (`text_range.start + relative`), `live=true`, `check_status="live"`, and
  suggestions revealed inline (`answer_revealed=true`, correction in
  `display_text`). The non-live path is unchanged (LT + LLM deep + sentence scan,
  persisted, on save / sentence completion).
- **Frontend** `use-grammar.ts`:
  - New live path: on edit, ~300ms debounce (Word-like), check the cursor
    sentence span **complete or incomplete**, no save gate, independent
    abort/dedup; merge live findings into the span and suppress overlapping
    polish. Decoupled from polish (separate triggers).
  - The full check (`runCheck`) stays save-gated + completed-sentence + LLM deep
    + persisted; on save it replaces the live findings in that span.
  - Plugin `merge` meta gains `live`: a live merge keeps persisted findings in
    the span and swaps only live ones (deduped by rule+span); a full merge
    replaces everything in the span. Extracted as pure `mergeIssueStates`.
  - Hover: live findings are pre-revealed (no DB reveal/teaching call); the
    explanation shows instantly. The card hides the teaching section for live
    findings (no persisted issue to teach from).
  - Accept: a live finding accepts **after save** — `saveNow()` → wait for the
    saved transition → full check on the sentence (persists a real issue) →
    match by rule+anchor → reveal → accept the chosen suggestion → range-scoped
    reconciliation. Persisted-issue acceptance is unchanged. Ignore on a live
    finding drops the decoration locally (no DB row).

## Consequences

- Deterministic grammar errors appear as you type (~300ms + local LT), without
  waiting for a full sentence, a save, or the LLM — like Word. Deeper/hidden
  errors still arrive via the save-time LLM analysis and are persisted for
  records, teaching and acceptance.
- Accepting a live finding costs one extra save+check round-trip (display was
  already instant); this is the approved accept-after-save trade-off.
- Short explanations for common errors remain rule-template/LT-message based
  (non-LLM, instant); LLM explanations only for LLM-detected errors.
- Contract 1.12.0: `grammar-check` request `live`; `GrammarIssue.live`;
  `check_status` adds `"live"`; live suggestions may be `answer_revealed=true`.
  No new endpoint (operation count unchanged); no DB migration (live is
  ephemeral, `live` is API-only).
- Tests: backend live-check (revealed deterministic issues, no LLM call, no
  persistence, no save/text gate, absolute offsets, stable ids, mode/ownership),
  planner v7 ordered outline; frontend `mergeIssueStates` units +
  `parseOutlineMarkdown` ordered units; E2E live display + ordered outline.
- Note: full-suite grammar tests can transiently fail when LanguageTool is cold
  or under concurrent load (15s timeout → empty issues); re-run with warm LT.
  Never run backend pytest and Playwright E2E concurrently (shared test DB).