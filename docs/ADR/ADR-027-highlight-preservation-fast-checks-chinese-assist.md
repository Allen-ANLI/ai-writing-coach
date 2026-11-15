# ADR-027: 接受保留其余高亮 + 检测提速 + 中文输入即推荐表达

**Status:** Accepted (2026-11-16, user directive)
**Related:** ADR-024/025/026 (fixes + extends), PRD FR-02/FR-03/FR-06,
contract 1.8.0.

## Context

User feedback after ADR-026:

1. Accepting **one** grammar correction or polish replacement made **all other
   underlines disappear**. Root causes (two layers):
   - Frontend: `applyContent` used `editor.commands.setContent`, replacing the
     whole document. ProseMirror maps every decoration position into the
     replaced range, so all grammar/polish decorations collapsed; only the
     re-checked sentence regained its underline.
   - Backend: `accept_issue_suggestion` and `validate_issue` marked **every
     other detected issue of the old revision stale**, so surviving highlights
     would also have been unusable (409 on reveal/accept).
2. Grammar/expression detection felt too slow. The debounce chain was
   autosave 1500ms + saved-effect 300/400ms + check debounce 900/1200ms before
   the request even fired (~3s + provider latency).
3. Chinese→English assist required selecting text and clicking a request
   button. The user wants: typing a Chinese word **immediately** shows usable
   English expressions, recommended **in the context of the whole sentence**,
   visible **without hover**, with the same card/interactions as expression
   polish (select, click/Tab replace, 查看更多 pagination, add to KB).

## Decision

1. **Minimal-diff content application**: `applyServerContent` computes the
   changed range with ProseMirror's diff algorithm (findDiffStart/findDiffEnd,
   reimplemented locally — the installed packages do not export them) and
   dispatches a single `replaceWith`. Decorations and the caret outside the
   range map through untouched. Used by every server-content application
   (accept, restore, rewrite, conflict reload).
2. **Range-scoped backend reconciliation**:
   - Accept: only issues whose anchor intersects the replaced range go stale;
     issues after it shift by the replacement delta; all survivors bump
     `source_server_revision` so they can be accepted in sequence.
   - Validate: survivors re-anchor by their anchor text near the expected
     position (shifted when the edit precedes them); only disappeared anchors
     go stale. Rule re-detection is scoped to the corrected sentence — the
     same rule firing in another sentence no longer re-anchors this issue
     across the text.
   - Frontend mirrors this with an `accept-shift` plugin meta (drop accepted +
     intersected issues, shift the rest's code-point offsets).
3. **Faster checks**: autosave debounce 1500→600ms; grammar saved-effect
   300→100ms, check debounce 900→350ms (120ms fast path when the edit just
   completed a sentence); polish saved-effect 400→120ms, scan debounce
   1200→400ms (150ms fast path). A sentence completed while a polish scan is
   in flight is queued, not dropped.
4. **Automatic Chinese expression assist**: the caret's Chinese run (CJK
   ideographs + Chinese punctuation) is detected on typing/IME commit/caret
   move; after a 250ms debounce (80ms after compositionend) the card opens
   automatically and requests `translations` with the whole sentence as
   context. Translation prompt v2 requires drop-in, sentence-fitting
   candidates and honors an `exclude` list; the card supports select,
   click/Tab replace (atomic server acceptance), 查看更多/上一页 pagination
   (per-page suggestion ids), add-to-KB, Esc dismiss, retry on error, and
   instant re-show from a small client cache. Selection-based assist is
   removed.
5. **Polish pagination fix**: each fetched page belongs to its own server
   suggestion; acceptance now targets the selected page's suggestion id
   (previously page-2 items were submitted against page 1's suggestion).

## Consequences

- Accepting one finding preserves every other highlight, and the preserved
  findings remain revealable/acceptable (integration + E2E verified).
- Underline latency floor drops from ~2.7–3.1s to ~0.9s before provider time;
  autosave writes are ~2.5× more frequent (still debounced, single-flight).
- Chinese input costs ~1 translation call per distinct run (cached client-side
  for re-entry; metered; 429 degrades to an error row with retry).
- Tests: apply-content diff/decoration-survival unit tests, Chinese-run unit
  tests, sequential accept + validation survival backend tests, translation
  exclude/prompt-v2 tests, E2E for highlight preservation (grammar + polish),
  automatic Chinese card with pagination/KB/Tab.