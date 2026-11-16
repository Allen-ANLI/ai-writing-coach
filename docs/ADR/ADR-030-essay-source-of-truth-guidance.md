# ADR-030: 范文为唯一事实源 — 确认/编辑必保证范文一致，移除大纲兜底

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-029 (model essay), PRD FR-04/FR-10.4, contract 1.10.0.

## Context

After ADR-029 the ghost still prompted from the outline for the user's essay.
Diagnosis (DB-verified): the user's confirmed outline predated ADR-029 and had
`model_essay=NULL`, so the frontend fell back to flattened outline ideas
(Chinese). The model-essay persistence code itself was correct (rolled-back
reproduction). Gaps: confirm did not generate an essay; manual outline edits
did not refresh it; workflow/legacy outlines had none.

User direction: the **model essay is the source of truth**. The planner must
write the essay FIRST and derive the outline FROM it (single call, explicit
ordering — two-stage rejected as redundant). The outline must also be manually
editable. The invariant to guarantee: **every confirmed outline carries a
model essay consistent with it**, so the outline-idea ghost fallback can be
removed permanently.

## Decision

1. **planner_chat v3** (single call): explicit STEP 1 write model_essay, STEP 2
   derive outline strictly from that essay (one sentence_idea per essay
   sentence, in order; paragraph titles match the essay). propose/revise both
   carry the essay; revise rewrites essay + re-derives outline.
2. **model_essay_generate v1 + ModelEssayResult**: write a complete essay from
   a given outline/thesis (used to bootstrap/refresh essay-less outlines).
3. **ensure_model_essay(db,user,outline_id)**: generate-from-outline when the
   essay is missing (LLM outside transactions, quota-guarded, usage-logged);
   no-op when present; raises ApiError on provider failure for graceful decay.
4. **confirm_outline guarantees an essay**: after confirming, if the essay is
   missing it is generated. Failure does not block confirmation (panel offers
   retry). Planner drafts with an intact essay confirm fast (no LLM).
5. **Manual outline edits expire the essay**: create/patch/delete node and
   patch thesis set `model_essay=NULL`; the next confirmation regenerates a
   matching essay. Regeneration is batched at confirm (not per node edit).
6. **Workflow outlines carry an essay**: processing.py generates it after the
   outline (failure defers to confirmation).
7. **POST /outlines/{id}/model-essay**: bootstrap the essay for an essay-less
   (e.g. legacy confirmed) outline; no-op when present. Contract 1.10.0 (105
   ops).
8. **Frontend**: ghost hints = `splitSentences(model_essay)` ONLY — the
   outline-idea fallback is removed (no essay → no hint). Planner panel shows
   a "生成范文指引" button for confirmed essay-less outlines (calls #7) and the
   collapsible 参考范文 when present. The outline tree remains a reference view.

## Consequences

- Ghost guidance always follows the model essay; outline and essay are
  consistent by construction (planner) or by regeneration (manual edits).
- The user's legacy outline gets an essay via one button click; thereafter
  every confirm/edit keeps the invariant.
- Confirm may incur one LLM call only when the essay is missing/stale; the
  common planner path stays fast.
- Tests: workflow essay, manual-edit expiry + confirm regeneration, thesis
  expiry, model-essay endpoint (bootstrap/no-op/ownership/usage v1), planner
  v3 usage; E2E ghost-from-essay flow. Real-provider smoke for essay-first
  planner + confirm bootstrap + rough advancement.