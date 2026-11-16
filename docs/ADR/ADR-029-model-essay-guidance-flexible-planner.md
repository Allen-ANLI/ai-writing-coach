# ADR-029: 范文驱动幽灵指引 + 自主结构构思 + 拼写/备选交互

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-024/025/026/027/028, PRD FR-02/FR-04, contract 1.9.0,
migration 0020.

## Context

User feedback after ADR-028:

1. Spelling errors showed the "请求详细解释" button — word-level spelling
   needs no LLM lesson.
2. Grammar cards listed alternatives as plain text; only the recommended
   suggestion was acceptable. The user wants to **select any alternative**
   and replace with it.
3. Ghost guidance stalled after a completed sentence. Diagnosis: the v1
   progress prompt demanded the sentence "genuinely cover" an abstract
   Chinese guidance idea (strict), each sentence was judged once against the
   current index only, and there was no catch-up — a false judgment (common
   with the real provider; the mock always returns true, hiding it in E2E)
   stuck the hint forever. The user wants **rough gist matching** to advance.
4. The planner should return **two artifacts**: a complete model essay
   (drives ghost hints sentence-by-sentence) and the outline OF THAT essay
   (shown in the left panel for reference).
5. The planner prompt must not hard-code the essay structure — the AI
   chooses an IELTS-appropriate structure freely, and the outline must still
   display correctly.

## Decision

1. **Spelling**: hover card state carries `issue.category`; the entire
   teaching section is hidden for `category === "spelling"`.
2. **Selectable suggestions**: all revealed suggestions render as chips
   (recommended badged, selected by default); `selectedSuggestionId` state +
   `selectSuggestion`; "接受修改" and Tab apply the **selected** suggestion
   (backend already accepted any suggestion_id).
3. **Model-essay guidance**: `PlannerChatResult.model_essay`;
   `writing_outlines.model_essay` (migration 0020, nullable); planner_chat v2
   returns essay + outline together; outline detail/list responses carry it.
   Frontend ghost hints = `splitSentences(model_essay)` when present, else
   the legacy flattened outline ideas (backward compatible). Panel outline
   card gains a collapsible "参考范文" view.
4. **Rough-match progress + catch-up**: ghost_progress v2 judges English
   sentence vs model sentence by **approximate meaning** (paraphrases,
   structure/detail differences and small grammar errors accepted; false
   only for a clearly different idea). On a false judgment the client judges
   the NEXT model sentence once more (same endpoint, server-cached) and jumps
   the index if it matches — writing ahead never stalls guidance.
5. **Flexible structure**: outline schema bounds relaxed (sections 1–8,
   paragraphs 1–8, ideas 1–10 — sanity caps only); planner_chat v2 and
   outline_generate v3 instruct "structure is your choice, follow IELTS
   conventions"; the outline must mirror the model essay (one paragraph node
   per essay paragraph, one Chinese sentence_idea per essay sentence) so the
   panel displays the real structure.
6. **LLM output tolerance**: the outline/planner AI schemas use
   `extra="ignore"` — real DeepSeek responses occasionally carry stray fields
   (observed: `title_note`), which `extra="forbid"` turned into a 502. Unknown
   fields are dropped, never persisted; required fields stay strict.

## Consequences

- Ghost guidance follows a concrete model essay and advances on gist, with a
  catch-up path; legacy outlines keep Chinese-idea guidance.
- Planner cost rises (full essay generation per propose/revise); metered and
  quota-guarded as before. Context-caching optimization (essay prefix +
  provider cache-hit metering) is analyzed and deferred to the next round.
- Tests: model-essay persistence/response, relaxed structure, stray-field
  tolerance, prompt v2 usage, spelling-no-teaching + alternative-selection
  E2E, model-essay ghost E2E; real-provider smoke PASS (322-word essay +
  AI-chosen 5-paragraph outline; paraphrase fulfilled=true with gist reason,
  unrelated sentence fulfilled=false).