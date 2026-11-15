# ADR-018: IELTS Question Bank — Original Content, License Gating, Text-Based Data

**Status:** Accepted (Slice 6, 2026-11-15)
**Supersedes/clarifies:** PRD FR-08 content target; traceability reconciliation R12.

## Context

PRD FR-08 requires an IELTS question bank (search, detail, tags, random,
favorites) and FR-08.5 targets 200–300 verified, licensed questions. Cambridge
IELTS past papers are copyrighted; reproducing them without a license is not
permitted. The PRD explicitly allows original practice questions. The ERD
(§11) already models `license_status`, `source_type` and publication flags.

## Decision

1. **Original content only at launch.** The seed is 60 practice questions
   written for AI Writing Coach: 18 Task 1 Academic (3 per chart type: line
   graph, bar chart, pie chart, table, process, map), 9 Task 1 General
   Training letters (3 per register: formal, semi-formal, informal), 33
   Task 2 (opinion, discussion, advantages/disadvantages, problem/solution,
   two-part) across 18 topic tags. Every question carries a Chinese
   `prompt_translation`. Growing toward the 200–300 target is ongoing content
   work, not a code blocker.
2. **Text-based Task 1 data.** Academic Task 1 prompts embed their data as
   structured text inside `prompt_text`, so the bank is self-contained
   without image assets. This keeps the practice loop fully functional while
   avoiding any third-party chart reproduction.
3. **License gate in the repository layer.** Only rows with
   `is_published = true AND license_status IN ('original','licensed')` are
   ever returned (list, detail, random, tags counts, favorite targets,
   essay-creation validation). `pending`/`restricted` rows stay invisible, so
   third-party content can be staged safely before clearance.
4. **Deterministic, idempotent seeding.** Seed rows use uuid5 ids derived
   from stable keys (`app/modules/ielts/seed_data.py`). Migration 0012 seeds
   online (offline `--sql` emits DDL only); `scripts/prepare_e2e_db.py`
   re-seeds because the pytest suite shares and truncates the test database.
   Existing keys must never change.
5. **Essay binding.** `essays.question_id` FK (deferred since 0003) is
   attached in 0012. Creating an essay with a `question_id` validates the
   question is published/permitted, requires `writing_type` to match the
   task (`ielts_task1`/`ielts_task2`), and autofills `question_prompt` from
   the bank when the client omits it — feeding the finalized editor's
   separate question section (ADR-016 §2.1).

## Consequences

- No copyright exposure at launch; third-party ingestion later requires
  explicit license clearance (flip `license_status` to `licensed`) — a
  material legal decision that stays with the user per Directive §6.
- Evaluations (Slice 7) can rely on `question_id` + `task_type` consistency.
- Favorites are idempotent (POST always 201, DELETE always 204 for permitted
  questions) and strictly user-scoped by composite primary key.
