# ADR-020: Workflow Persistence, LangGraph Scope, and Ghost-Text Semantics

**Status:** Accepted (Slice 8, 2026-11-15)
**Related:** SD §9, API Spec §14–15, ERD §12, ADR-016 (finalized UX), ADR-019 (background processing).

## Context

SD §9 requires LangGraph for exactly three multi-step, human-confirmed flows
(writing planner, learning extractor, personalized study planner) and forbids
routing simple features through it. The contract exposes business status and
events, never graph internals. PRD FR-10.4 requires outline-driven ghost text
that never writes into the body without user acceptance.

## Decision

1. **LangGraph where it earns its place.** The three workflows are real
   `StateGraph`s (langgraph 1.x): the planner has a conditional quality-check
   loop (regenerate once if the structure is invalid), the extractor an
   extract→dedupe pipeline, the study planner a context-gather→plan pipeline.
   Everything else (grammar, polish, translation, evaluation, CRUD) stays a
   direct service call per SD §9.4.
2. **Durable pause/resume at the business layer.** Graph runs use an
   in-process `MemorySaver` checkpoint; the durable state is the `workflows`
   row (status, input, result) plus append-only `workflow_events`. A run
   completes into `awaiting_confirmation`; `resume` applies the result through
   the owning business services (confirmed outline, KB saves) or re-runs on
   `revise`. This survives process restarts — a MemorySaver-only design would
   not — and keeps the API free of graph internals. A shared checkpoint saver
   can replace MemorySaver when workers are introduced.
3. **Confirmation is mandatory.** Nothing a workflow produces reaches user
   data until an explicit `confirm`/`continue`. `reject` closes the workflow
   without side effects. The study planner's confirmed suggestions become
   learning plans/tasks in Slice 9 (deterministic scheduling stays server-side).
4. **Ghost text = explicit insertion.** A confirmed plan surfaces the next
   sentence idea as a dashed hint bar in the editor. The text is inserted only
   when the user clicks Insert (at the caret, as a new paragraph). There is no
   automatic inline completion and no Tab binding — Tab remains reserved for
   grammar correction acceptance (ADR-016 §2.5).
5. **Outline lifecycle.** `generating → draft → confirmed` (or `failed`);
   only drafts are editable; confirmation locks the outline and stamps
   `confirmed_at`. Outlines are bound to the essay owner via composite FK and
   never modify essay content.

## Consequences

- Workflow UX is poll-based (MVP per API Spec §15); SSE can be added later
  without contract changes to the status/events shapes.
- The planner dialog uses the outlines API (quick path); the full workflow
  API is exercised by the study-planner card and covered by integration tests
  for all three types.
- Restart-safety is tested at the business layer; graph-internal checkpoint
  replay is not part of the public contract.
