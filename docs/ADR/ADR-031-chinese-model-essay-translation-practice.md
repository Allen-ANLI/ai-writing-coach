# ADR-031: 范文为中文 — 幽灵提示是翻译练习而非抄作文

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-029/030 (model essay guidance), PRD FR-04.

## Context

ADR-030 stored the model essay in English and the ghost showed English
sentences. The user corrected the pedagogy: **ghost hints must be CHINESE**.
The learner practices by translating a Chinese idea into English themselves;
showing English sentences would reduce the exercise to copying and teach
nothing. The model essay must therefore be the Chinese translation of an
IELTS-quality English essay.

## Decision

1. **planner_chat v4** (single call): STEP 1 internally compose a complete
   ENGLISH essay per IELTS conventions (not returned); STEP 2 translate it
   sentence-by-sentence into natural Simplified Chinese — `model_essay` is
   this CHINESE translation only (each sentence ends 。！？, one per English
   sentence, paragraph breaks kept, no English); STEP 3 derive the outline
   from the essay. propose/revise carry the Chinese essay; revise rewrites it.
2. **model_essay_generate v2**: same English→Chinese method for bootstrapping/
   refreshing essay-less outlines; returns the Chinese translation.
3. **ghost_progress v3**: cross-lingual rough match — the learner's ENGLISH
   sentence vs the CHINESE model sentence; fulfilled when the English conveys
   the gist (paraphrase/detail-tolerant, not 100%), false only for a clearly
   different idea.
4. **Chinese sentence splitting**: `splitSentences` (document-text.ts) now
   recognizes full-width terminators 。！？ (and closing 」』”’）》】) as sentence
   ends WITHOUT requiring a following space (Chinese has no inter-sentence
   spaces). English .!? logic unchanged. Ghost hints = splitSentences(Chinese
   model_essay).
5. **Mock + UI**: mock planner/model-essay return a deterministic Chinese
   essay; panel intro and 参考范文 label state the guidance is Chinese for
   translation practice.

## Consequences

- Ghost guidance is Chinese; the learner writes English from meaning — genuine
  translation practice. The English essay exists only inside the LLM call to
  guarantee IELTS quality; only the Chinese essay + outline are stored/returned.
- Cross-lingual progress judgment advances on gist.
- Tests: Chinese splitSentences units (terminators, closers, trailing
  incomplete, paragraph breaks); planner v4 / model_essay v2 / ghost_progress
  v3 usage; E2E ghost shows the Chinese sentence and advances on an English
  translation. Real-provider smoke for Chinese essay generation + cross-lingual
  advancement.