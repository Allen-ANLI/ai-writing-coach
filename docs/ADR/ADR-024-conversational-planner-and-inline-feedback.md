# ADR-024: 对话式构思 + 悬浮直显语法反馈 + 中文界面

**Status:** Accepted (2026-11-15, user directive — overrides ADR-016 §2.3–2.6 and the
ADR-020 ghost-text banner)
**Related:** PRD FR-02/FR-10, API Spec §6–7/§14, contract 1.5.0, migration 0018.

## Context

User feedback after using the editor:

1. Grammar checking appeared "dead": checks require an active writing session, but
   nothing started one automatically, so writing without clicking "Start writing
   session" produced no feedback and no teaching requests ever reached the LLM.
2. The blurred-correction → click-to-reveal → Tab flow was undiscoverable; Tab
   seemed broken because it only worked after pinning.
3. The Plan dialog + left document-outline tree did not match the desired workflow:
   the learner wants to **talk to an agent** in the left panel to agree on the
   structure before writing and to revise it mid-writing.
4. The ghost-text banner (English idea titles, above the editor) was not the wanted
   experience: gray **Chinese** inline guidance at the caret, based on the agreed
   outline, was missing.
5. The product targets mainland-China users; the UI must be Chinese except essay
   prompts and other necessary English content.

## Decision

1. **Auto session.** Opening the editor auto-creates an assisted/free_writing
   session when the essay has no sessions or the latest session was submitted
   (continue writing). An explicitly cancelled session is NOT auto-recreated, so
   independent/exam modes remain switchable via the session bar. Grammar checking
   works immediately without any manual step.
2. **Hover shows everything.** Hovering an underlined issue fetches the stored
   correction (existing reveal endpoint — server records the reveal, preserving
   the "no unrevealed leak" invariant) AND the contextual teaching (existing
   teaching endpoint, cached per issue+revision+context) in parallel. The card
   shows the short explanation, the recommended correction directly (no blur,
   no reveal click), alternatives, and the detailed explanation with
   loading/error/retry states. **Tab accepts while the card is visible**; Esc
   closes; Alt+I ignores. Clicking an error only places the caret. The standalone
   teaching card, teaching icon, Alt+R/Alt+T and click-to-teach are removed.
3. **Conversational planner (left panel).** New endpoints
   `POST /essays/{id}/planner/chat` and `GET /essays/{id}/planner/messages`
   (contract 1.5.0, +2 ops → 101). Chat history persists in `outline_chat_messages`
   (migration 0018, same-owner composite FK). The agent (prompt `planner_chat v1`)
   replies in Chinese and either discusses, proposes a first outline, or revises
   the current one; proposed/revised outlines are stored as regular
   `writing_outlines` drafts via `save_generated_outline` and linked from the
   assistant message. The user confirms in the chat card (existing confirm
   endpoint). Confirming archives earlier confirmed versions — one current plan
   per essay. The Plan button, planner dialog and document-outline tree are
   removed; the left panel (and mobile drawer) is the chat.
4. **Chinese outline guidance.** `outline_generate v2` and `planner_chat v1`
   produce Chinese section/paragraph titles and sentence_ideas (writing guidance,
   never essay sentences); thesis_statement stays English (usable in the essay).
   v1 prompts remain immutable for attribution.
5. **Inline gray ghost hints.** A ProseMirror widget decoration shows the next
   Chinese sentence idea at the caret when the paragraph is empty or has fewer
   written sentences than ideas (paragraph ordinal → outline paragraph). It is
   never persisted, never counted in words, disappears on typing/caret move, and
   can be dismissed by click. It is guidance only — no Chinese is inserted into
   the English essay (AI-never-writes invariant preserved).
6. **Chinese UI.** All user-facing strings are Simplified Chinese; essay content,
   question prompts, IELTS question text and code identifiers stay English. No
   i18n framework introduced (direct literals); backend error envelopes unchanged
   (contract), common codes mapped to Chinese at display sites.

## Consequences

- Grammar feedback works on first open; the LLM teaching path is exercised by
  normal hovering (quota-guarded and usage-logged as before).
- Hover-triggered teaching costs one LLM call per unique issue/revision/context
  (server cache prevents repeats); the free-tier quota still applies.
- The planner chat is synchronous (8–15 s per turn with the real provider); the
  UI shows a thinking indicator. Mock provider deterministically proposes so E2E
  can exercise confirmation.
- ADR-016 §2.3–2.6 (blur/reveal/teaching-icon/no-submit) is superseded for the
  feedback interaction; the no-Submit-during-writing rule stays. ADR-020's
  ghost-banner is superseded by inline hints; its "explicit user action, never
  auto-write" invariant stays.
- Tests updated: grammar/outlines/sessions/expressions/editor/auth/billing/
  evaluations/learning/ielts/slice9/privacy specs; new backend planner-chat tests
  (7) and the runtime-dependency guard.