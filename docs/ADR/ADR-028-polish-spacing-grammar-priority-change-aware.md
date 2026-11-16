# ADR-028: 润色选项空格 + 语法优先 + 变更感知的高亮 reconciliation

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-026/027 (fixes), PRD FR-02/FR-03.

## Context

User feedback after ADR-027:

1. Polish option words sometimes rendered **without spaces** ("reallylike").
   Root cause: `wordDiff` tokenized on whitespace and re-joined words *within*
   a segment with spaces, but segment **boundaries** (changed↔unchanged) lost
   the separating space entirely.
2. Where a fragment has **both a grammar error and an expression issue**,
   polish showed first. The user wants **grammar first**: fix the grammar,
   then polish may suggest on that fragment.
3. After accepting a polish replacement, a **stale grammar underline**
   (e.g. spelling) reappeared on the *old* word that no longer exists.
   Root causes: grammar decorations were carried over by position mapping
   without verifying the anchor text still matches; the expression-accept
   backend path never reconciled `writing_issues` against the edited range.
   The system must recognize **what changed** and re-check that region,
   never blindly reuse old detections — while unmodified places keep their
   correct highlights and never receive stale/wrong ones.

## Decision

1. **Whitespace-preserving wordDiff**: tokens carry their trailing whitespace
   (`/\S+\s*/g`); segments concatenate to exactly the replacement string
   (invariant unit-tested, incl. multiple/leading spaces). Leading whitespace
   is emitted as an unchanged segment.
2. **Anchor-intact invariant on server applies**: `applyServerContent` marks
   its transaction (`awcServerApply` meta). Both grammar and polish plugins,
   on such transactions, drop any decoration whose current document text no
   longer equals its anchor text. User typing is unaffected (the
   underline-then-validate self-correction flow stays intact).
3. **Grammar priority**: polish scan results overlapping an active grammar
   issue are suppressed; when a grammar check merges findings, overlapping
   polish fragments are removed. After the grammar is fixed (accept /
   validated self-edit) the revision bump re-scans polish; ignoring a grammar
   issue dispatches a polish rescan event. Non-overlapping findings coexist.
4. **Change-aware backend reconciliation on expression accept**:
   `accept_suggestion` reconciles detected `writing_issues` against
   `modified_range` — intersecting anchors go stale, later anchors shift by
   the length delta, survivors bump `source_server_revision` (mirrors the
   grammar-accept logic from ADR-027). The client re-checks the changed
   sentence via the existing saved-effect pipeline.

## Consequences

- Option rendering can no longer glue words together (unit + E2E assert
  "really like" with the space).
- A replaced region never shows old-word underlines; the region is re-checked
  and only fresh findings appear. Unmodified regions keep correct highlights.
- Grammar and polish no longer compete on the same fragment; ordering is
  grammar → fix → polish.
- Tests: wordDiff spacing/invariant units, expression-accept grammar
  reconciliation integration test, E2E grammar-priority lifecycle and
  polish-accept preservation/no-stale flows.