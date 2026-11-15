# ADR-025: 语法检查可靠性 + 整句识别 + 句子级写作指引

**Status:** Accepted (2026-11-15, user directive)
**Related:** ADR-024 (supersedes its ghost-hint mechanics), PRD FR-02/FR-10,
contract 1.6.0, SD §5.3–5.4.

## Context

User reported: grammar checking "dies after a few sentences"; only word-level
errors are detected; ghost hints stop after one or two sentences and should
instead guide sentence-by-sentence with completion judgment; the hint toggle
belongs in the planner panel.

Root causes found (code + live LanguageTool probes):

1. **Check scheduling**: the debounce checked only the sentence containing the
   cursor at fire time. Typing ". " quickly moves the cursor past the completed
   sentence → no check ever fires.
2. **Stale discard**: autosave bumps the revision during the ~1s LT check →
   the response was discarded wholesale.
3. **Global replace**: the frontend `set` meta replaced ALL underlines with the
   latest sentence's findings; the backend staled every other issue at the same
   revision on each single-sentence check.
4. **Detection breadth**: LanguageTool misses high-frequency Chinglish
   ("I very like this book", "suggest me to go", "although...but" — verified
   zero matches). The LLM only confirmed LT-flagged fragments and never scanned
   the whole sentence; uncertain LT hits were silently dropped on LLM
   rejection/failure.
5. **Ghost hints**: paragraph-ordinal based, shown only in empty paragraphs or
   at paragraph end, exhausted after 1–4 ideas, click-to-dismiss.

## Decision

1. **Sentence selection**: check the completed sentence at the cursor, or the
   last completed sentence before the cursor; dedupe unchanged sentences
   client-side (`use-grammar.ts`).
2. **Stale reconciliation**: apply findings when the checked sentence is still
   verbatim at the same range despite a revision bump; otherwise drop and let
   the saved-effect re-check.
3. **Range-scoped merge**: frontend `merge` meta replaces only issues inside
   the checked range; backend stale-marking is limited to that range.
   Multi-sentence underlines coexist.
4. **Whole-sentence LLM scan** (`grammar_sentence_check v1`): every completed
   sentence gets a full-sentence analysis for errors rules miss (tense, word
   order, verb patterns, prepositions, conjunction duplication, collocations).
   Model offsets are validated against the sentence text (invalid spans
   dropped, drifted anchors relocated verbatim). Results merge/dedupe with
   rule findings; cached per (user, revision, sentence hash). On provider
   failure, uncertain LT hits are kept at confidence 0.5 (check marked
   partial) instead of dropped. Quota-guarded and usage-logged.
5. **Sentence-level guidance loop**: the confirmed outline is flattened into
   ordered sentence ideas. The current idea shows persistently at the caret
   while the sentence is unfinished. On sentence completion,
   `POST /essays/{id}/planner/progress` (`ghost_progress v1`) judges semantic
   fulfillment: fulfilled → advance to the next idea; not fulfilled → keep the
   current idea. Judgments cached per (user, idea, sentence hash); provider
   failure degrades to advance-without-blocking. Guidance runs through the
   whole outline; exhaustion shows "大纲已完成" in the panel.
6. **Toggle in the planner panel**: `preferences.ghost_hints_enabled` (JSONB,
   no migration) drives a switch in PlannerChatPanel; click-to-dismiss removed.

## Consequences

- Grammar feedback survives fast typing and concurrent autosaves; errors from
  all sentences stay visible.
- Detection covers Chinglish and grammar beyond LT's rule set; cost is ~1 LLM
  call per completed sentence (scan) + 1 per guidance judgment, all metered.
- Rule-first instant feedback is preserved; deterministic hits never wait for
  the LLM.
- Tests: sentence-scan merge/offset validation, range-scoped stale, progress
  endpoint (fulfilled/not/cached/degraded/quota/ownership), preferences toggle,
  multi-sentence E2E, ghost toggle + advance E2E.