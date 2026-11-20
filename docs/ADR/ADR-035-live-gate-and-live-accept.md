# ADR-035: 即时语法报错门槛 + live-accept 原子接受

**Status:** Accepted (2026-11-20, user directive)
**Related:** ADR-024/025/027/034, PRD FR-02, contract 1.13.0.

## Context

Two user-reported defects (2026-11-20), both rooted in the ADR-034 live path:

1. **Incomplete sentences were judged as errors.** ADR-034's live check ran on
   the cursor sentence "complete or incomplete" (a user decision at the time).
   In practice, finishing a word + typing a space + a 300ms pause produced a
   grammar underline while the writer was still composing (e.g. "He go…" on
   the way to "He goes…", "I am study…" before "studying" is finished). The
   user now requires: 句子尚未完成，不能判定为错误 — restoring the original
   2026-11-15 §5 principle ("trailing input without punctuation … must not be
   checked prematurely") that ADR-034 had overridden for the live path.
2. **Accepting a spelling correction sometimes did nothing.** Spelling hits
   are deterministic, so they almost always appear as ephemeral live findings.
   ADR-034's acceptance chain was `saveNow → waitForSaved(≤4s) → full
   grammarCheck (incl. the LLM whole-sentence scan, 1–3s+, 429 when quota is
   exhausted) → match rule+anchor → reveal → accept`. Every failure path
   silently closed the card:
   - the user keeps typing during the multi-second chain (the card does not
     block input) → autosave bumps `server_revision` → 409 at the full check
     or at accept;
   - `waitForSaved` timeout, or save in `conflict`/`error` state;
   - the full check does not re-hit the same rule+anchor (e.g. LanguageTool
     cold-start timeout returns empty — noted in ADR-034);
   - the persisted path early-returned silently whenever autosave was not
     `saved` (clicking accept within the 450ms debounce window after typing —
     the most common "点了没反应" case);
   - non-409 errors were unhandled.

User decisions (ask_user_question, 2026-11-20): gate = **spelling instant on
finalized words, grammar waits for sentence completion**; accept = **new
atomic live-accept endpoint** (recommended option).

## Decision

### Live gate (revises ADR-034 "including incomplete input")

- `grammar-check` request gains `sentence_complete: bool = false`.
- `_live_check` surfaces a deterministic finding only when:
  - **spelling**: the misspelled word is *finalized* — a following character
    exists and is not alphanumeric / `'` / `’` / `-` (whitespace or punctuation
    finalizes the token; end-of-text means the writer may still be typing it,
    so it is suppressed). A complete span also finalizes its last word: a
    paragraph break ends the span before the separator, so the following
    character is not visible in the submitted text;
  - **all other categories**: `sentence_complete` is true (terminator typed or
    paragraph break, per `splitSentences`).
- Frontend `scheduleLiveCheck` sends `span.complete`; span selection is
  unchanged (cursor sentence, fallback to the last sentence before the
  cursor). The save-gated full check still requires completed sentences.
- Effect: no grammar verdicts mid-composition; Word-like spelling feedback on
  completed words; sentence completion still triggers instant live findings
  (~300ms, no save/LLM gate), persisted later by the full check.

### Atomic live-accept (revises ADR-034 accept-after-save trade-off)

- New `POST /essays/{essay_id}/issues/live-accept` (`LiveAcceptRequest`:
  `session_id`, `base_revision`, `client_revision`, `rule_id`, `start_offset`,
  `end_offset`, `anchor_text`, `replacement`; offsets are absolute
  `unicode_codepoint`).
- Server flow: ownership/session/mode checks → lock working document +
  `base_revision` check (409 `WORKING_DOCUMENT_CONFLICT`) → verify the anchor
  at the offsets, nearest-occurrence re-anchor on drift (409 `STALE_AI_RESULT`
  when the anchor disappeared) → close the read transaction → re-run the rule
  engine on the containing sentence (**no LLM, no billing**) → require an
  exact deterministic re-hit (rule + anchor + span; 409 `STALE_AI_RESULT`
  otherwise) → require `replacement ∈` server-derived suggestions (422
  `VALIDATION_ERROR` otherwise) → short write transaction re-checks the
  revision → find-or-create the issue row (an existing detected row with the
  same rule+span is reused, never duplicated) → apply through the shared
  `accept_issue_suggestion` transaction (revision increment, issue resolution,
  suggestion acceptance, Edit Event, range-scoped reconciliation of other
  issues).
- The client only picks an option the server already offered (the live
  finding's `display_text`); free client replacement text is rejected. The
  "acceptance applies a server-stored suggestion" invariant is preserved.
- Frontend `acceptLiveIssue` becomes `saveNow → waitForSaved → liveAccept
  (single call) → reconcileAfterAccept`. The race window shrinks from a
  multi-second LLM chain to one save + one fast rule-only request, and
  acceptance no longer depends on LLM availability or quota.
- Persisted acceptance: when autosave is not `saved`, flush the save and wait
  for it instead of silently returning.
- **Visible failure feedback**: `HoverCardState` gains `accepting` /
  `acceptError`; the card shows 应用中… while in flight and an error message
  with a 重试 button on failure (409 → "文档已更新，修改未应用。请重试。" +
  re-check; save conflict/error → explicit message). No failure path silently
  closes the card anymore. Tab acceptance is guarded while accepting.

## Consequences

- Incomplete input is never judged prematurely for grammar; spelling stays
  Word-like on finalized words (a completed word's spelling cannot be fixed
  by typing more words, so it is safe to judge mid-sentence).
- Live acceptance is fast, LLM-free, conflict-resistant and retryable;
  failures are visible instead of silent.
- Contract 1.13.0: +1 operation (107 total), `grammar-check`
  `sentence_complete`, `LiveAcceptRequest` schema. No DB migration (reuses
  `writing_issues` / `issue_suggestions`).
- Known limitation (pre-existing, narrowed): if the user types while an
  accept request is in flight, reconciliation applies the server document;
  the window is now sub-second instead of multi-second. A concurrent-edit
  merge for acceptance remains future work.
- Tests: backend live-gate tests (incomplete suppresses grammar, complete
  shows it, default-false, finalized/unfinalized/punctuation spelling) and
  live-accept tests (atomic apply + no LLM/usage, mid-sentence accept,
  conflict no-partial-write, foreign replacement 422, disappeared anchor 409,
  unknown rule 409, persisted-row reuse, other-issue preservation, ownership,
  independent mode). E2E: the ADR-034 "incomplete input is live-checked
  instantly" assertion is inverted (no findings before completion, instant
  live finding after), plus a new mid-sentence live-spelling acceptance test.