# ADR-026: 片段级润色 + 按需结构化教学 + 文末指引 + 错误记录

**Status:** Accepted (2026-11-15, user directive)
**Related:** ADR-024/025 (supersedes parts), PRD FR-02/FR-03/FR-04, contract 1.7.0,
migration 0019.

## Context

User feedback after ADR-025:

1. Ghost hints followed the caret; they should sit at the **end of the written
   text**. Updating the outline mid-writing restarted guidance at sentence 1
   instead of resuming from the current position.
2. Detailed grammar explanations auto-loaded on hover (cost) and rendered as a
   text wall; the user wants an explicit **request button**, structured/visual
   output, and the order **grammar knowledge point first, then a brief
   sentence-specific reason**.
3. Accepting corrections sometimes duplicated text: the LLM returned a
   whole-sentence rewrite while acceptance replaced only the anchor fragment,
   leaving the words before it in place.
4. Expression polish was selection-triggered and whole-sentence; the user wants
   **sentence-completion-triggered fragment-level** polish: automatic amber
   underline on unnatural fragments, 3 selectable options with the replaced
   words highlighted (unchanged context in normal color), click/Tab one-key
   replacement, pagination for 3 more options (and back), add-to-knowledge-base.
   Natural sentences must produce nothing (prompt-enforced).
5. Completed essays need a reviewable record of grammar errors and expression
   optimizations, categorized in one place.

## Decision

1. **Ghost placement & resume**: widget renders at the end of the last non-empty
   block (empty doc: first paragraph). On outline change the index resumes at
   `min(completed_sentence_count, ideas.length)`; the fulfillment loop is kept.
2. **Teaching v2 (on demand)**: hover card shows a "请求详细解释" button; the
   request fires only on click. `teaching v2` returns
   `{title, knowledge_point{explanation, pattern, examples[wrong/correct/note]},
   sentence_reason, recommended_correction}`. The client renders it visually:
   knowledge-point card with a structure-formula chip and wrong→correct
   contrasts first, then the brief sentence reason. Cache filtered by
   `prompt_version='v2'`.
3. **Duplication-free acceptance**: prompts (deep_check v2, sentence_check v2)
   require drop-in fragment replacements; `_resolve_replacement_range`
   deterministically widens the range when a suggestion contains the whole
   sentence or overlaps leading/trailing context; no-op suggestions → 422.
4. **Fragment polish v2**: `POST /essays/{id}/expressions/polish-sentence`
   (scan or more-options via fragment_anchor+exclude). `expression_polish v2`
   returns fragments with sentence-relative offsets + exactly 3 drop-in
   options, empty when natural. Items store absolute offsets (migration 0019).
   Frontend: amber dashed underline extension, option card with client-side
   word-level LCS diff highlighting, select + click/Tab replace (existing atomic
   accept), pagination, add-to-KB. Selection-based assist keeps only
   Chinese→English translation.
5. **Records**: `GET /essays/{id}/expression-suggestions` + existing issues
   list power a "错误与优化记录" dialog with two tabs (语法错误 / 表达优化),
   showing statuses (已解决/已忽略/待处理; 已采用/未替换).

## Consequences

- Teaching cost is user-controlled; polish adds ~1 LLM call per completed or
  edited sentence (metered; 429 degrades silently).
- Acceptance can no longer duplicate leading words (unit + integration tests).
- Old v1 teachings remain in storage but are never served; prompts v1 kept for
  attribution.
- Tests: replacement-range unit/integration, polish scan/empty/pagination/
  records/mode/ownership, teaching v2 structure, word-diff unit, E2E for all
  flows above.