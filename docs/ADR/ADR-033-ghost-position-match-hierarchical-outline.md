# ADR-033: 幽灵位置+嵌入匹配定位 + 层级化 Markdown 大纲

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-029/030/031/032, PRD FR-04, contract 1.11.0.

## Context

1. **Ghost positioning bug**: after deleting sentences and rewriting, the ghost
   hint showed the wrong sentence. Root cause: the index only advanced
   (`maybeJudgeProgress` fired only when the completed-sentence count increased
   and `processedSentencesRef` held a high-water mark); deletion never retreated
   the index.
2. The user asked how the ghost works (LLM vs pure code) and whether RAG would
   be better.
3. The outline was flat and wordy; the user wants a hierarchical outline where
   each idea leads with a few-word summary (e.g. "原因1：生活节奏快"), then a
   concise explanation + example, then nested sub-points — displayed as
   always-expanded nested indentation.

## Decision

### Ghost = position + embedding content match
- **Tech clarified**: hint TEXT = the LLM-generated model essay's Chinese
  translation (produced once at planning); DISPLAY = pure code (ProseMirror
  widget); ADVANCEMENT = now position + embedding (was per-sentence LLM
  judgment). **RAG is not a fit** — RAG retrieves corpus knowledge to augment
  generation; the ghost is a fixed pre-generated essay shown sentence by
  sentence, with no retrieval need. Embedding cosine similarity is the right
  tool for content matching.
- New `POST /essays/{id}/planner/match` (`chat.match_position`): returns the
  number of LEADING learner sentences whose embedding cosine similarity to the
  corresponding model sentence ≥ `ghost_match_threshold` (default 0.55).
  Position-based → deleting sentences retreats the index; rewriting re-locates.
  **Mock embeddings carry no semantics → degrade to pure position**
  (matched = sentence count); a real embedding endpoint enables semantic
  gating; embedding failure also degrades to position (never block the writer).
- Frontend: replaced the monotonic `maybeJudgeProgress`/`processedSentencesRef`
  machinery with a debounced (~400ms) `syncGhostPosition` that reads the current
  completed sentences, calls match, and sets the index = clamp(matched). Runs on
  edit, on plan/toggle change, and after initial content load. Result cached by
  sentence-text key to skip redundant calls. `ghost_progress` LLM endpoint is
  retired from the editor (kept backend-side, unused).

### Hierarchical markdown outline
- `planner_chat v6` / `outline_generate v5`: `outline_md` is rich nested
  markdown — `## ` section, `### ` paragraph, `- **短概括**：详解。例如：例子。`
  per idea (few-word bold label first), `  - ` nested sub-points. Structured
  `sentence_idea.title` stays a short label.
- Frontend `outline-markdown.tsx`: `parseOutlineMarkdown` now captures bullet
  indent depth; renders always-expanded nested indentation (bold label + detail
  via inline `**bold**`, deeper sub-points indented further, ◦ vs • markers).

## Consequences

- Ghost hint always reflects the writer's actual position; deletion retreats it
  correctly. In dev (mock embeddings) this is pure position; semantic gating
  activates once a real embedding endpoint is configured (launch blocker).
- Outline is scannable: summary → explanation/example → sub-points.
- Tests: match endpoint (mock degrade, cosine gating via stub, failure degrade,
  deletion retreat, ownership), planner v6 nested outline + alignment,
  parseOutlineMarkdown depth units; E2E ghost advance/retreat + nested outline.
- Note: full-suite grammar tests can transiently fail when LanguageTool is cold
  or under concurrent load (15s timeout → empty issues); re-run with warm LT.