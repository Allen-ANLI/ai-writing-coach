# ADR-032: 英文范文 + 逐句对齐中文翻译 + Markdown 大纲；响应时序说明

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-029/030/031, PRD FR-04, migration 0021.

## Context

1. The user wants the planner to return THREE artifacts: the ENGLISH model
   essay, its CHINESE translation, and a Chinese outline derived from the
   essay. ADR-031 stored only Chinese; the English source is now kept too.
2. **Sentence alignment is critical**: the Chinese translation must be split
   by the English essay's sentence boundaries (1 Chinese sentence per English
   sentence). Otherwise a Chinese hint may span two English sentences; the
   learner finishes the first English sentence (types a period, expresses
   part of the meaning), the rough-match judgment advances the hint, yet the
   original hint sentence was not actually complete — guidance skips ahead.
3. The outline was wordy and hard to read; the user wants a clean, structured
   **Markdown** outline with a matching frontend rendering.
4. The user asked how grammar/polish response timing is designed (feels slow).

## Decision

1. **Schema/storage** (migration 0021, additive): `writing_outlines.model_essay`
   = ENGLISH source; new `model_essay_zh` = sentence-aligned Chinese translation
   (drives ghost hints); new `outline_md` = markdown outline. `OutlineData`,
   `PlannerChatResult` (model_essay + model_essay_zh), `OutlineGenerationResult`
   (outline_md), `ModelEssayResult` (model_essay + model_essay_zh) updated.
2. **planner_chat v5** (single call): STEP 1 compose English essay; STEP 2
   translate STRICTLY sentence-by-sentence — model_essay_zh has EXACTLY the
   same sentence count as model_essay, never merge/split; STEP 3 derive
   structured outline (short Chinese phrases ≤20 chars); STEP 4 outline_md
   (## section / ### paragraph / - numbered bullets, terse).
3. **model_essay_generate v3**: same English + 1:1 Chinese method for
   bootstrap/refresh. **outline_generate v4**: adds outline_md.
4. **Ghost hints = splitSentences(model_essay_zh)** (Chinese, 1:1 with English).
   confirm guarantees model_essay_zh; manual outline edits expire essay + zh +
   outline_md (regenerated on confirm; outline_md falls back to node tree until
   re-planned).
5. **Frontend**: lightweight dependency-free `OutlineMarkdown` renderer
   (parseOutlineMarkdown pure fn + styled blocks: section/paragraph/bullet,
   **bold** inline); panel renders outline_md (fallback PlanBranch), and the
   参考范文 details show both Chinese translation and English essay.
6. **Timing** (explanation + modest optimization): checks are gated on a
   completed autosave (backend validates text_range against the saved doc).
   Floor = autosave debounce + saved-effect delay + check debounce; the
   dominant latency is the LLM call itself (1–3s), not the debounce. Reduced
   autosave 600→450ms, grammar saved-effect 100→70ms, polish 120→80ms (~200ms
   saved). Fast-path debounces (grammar 120 / polish 150 on sentence completion)
   unchanged. LLM latency is addressed by the upcoming context-caching round.

## Consequences

- Ghost guidance is Chinese AND sentence-aligned to the English essay, so a
  completed English sentence maps to exactly one finished hint — no premature
  advancement.
- Outline is scannable markdown; English essay available for reference.
- Tests: sentence-count alignment, English+Chinese+markdown storage, manual
  edit expiry of all three, confirm regeneration, endpoint v3, parseOutlineMarkdown
  units; E2E markdown outline + bilingual essay + Chinese ghost. Real-provider
  smoke for aligned translation + markdown.