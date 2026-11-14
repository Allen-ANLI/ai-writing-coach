/**
 * Text position mapping between the three coordinate systems (AGENTS §4):
 *
 * - API offsets are Unicode code points (`unicode_codepoint`).
 * - JavaScript strings are indexed in UTF-16 code units.
 * - ProseMirror positions count UTF-16 units plus node boundary tokens.
 *
 * Never mix them: convert explicitly at the boundary. These helpers are pure
 * and unit-tested with emoji / CJK text.
 */

import type { Node as ProseMirrorNode } from "@tiptap/pm/model";

/** Number of Unicode code points in a string (astral characters count once). */
export function codepointLength(text: string): number {
  return Array.from(text).length;
}

/** Convert a code-point offset to a UTF-16 offset. Clamps to text length. */
export function codepointToUtf16(text: string, codepointOffset: number): number {
  if (codepointOffset <= 0) {
    return 0;
  }
  let utf16 = 0;
  let seen = 0;
  for (const ch of text) {
    if (seen >= codepointOffset) {
      break;
    }
    utf16 += ch.length;
    seen += 1;
  }
  return utf16;
}

/** Convert a UTF-16 offset to a code-point offset. Clamps to text length. */
export function utf16ToCodepoint(text: string, utf16Offset: number): number {
  if (utf16Offset <= 0) {
    return 0;
  }
  let utf16 = 0;
  let seen = 0;
  for (const ch of text) {
    if (utf16 >= utf16Offset) {
      break;
    }
    utf16 += ch.length;
    seen += 1;
  }
  return seen;
}

export interface PmRange {
  from: number;
  to: number;
}

export interface CodepointRange {
  start: number;
  end: number;
}

/**
 * Map a code-point range over the document's concatenated text to ProseMirror
 * positions. Returns null when the range is outside the document text.
 */
export function codepointRangeToPm(
  doc: ProseMirrorNode,
  start: number,
  end: number,
): PmRange | null {
  if (start < 0 || end < start) {
    return null;
  }
  const total = codepointLength(doc.textContent);
  if (end > total) {
    return null;
  }
  const from = codepointOffsetToPm(doc, start);
  const to = codepointOffsetToPm(doc, end);
  if (from === null || to === null) {
    return null;
  }
  return { from, to };
}

function codepointOffsetToPm(doc: ProseMirrorNode, offset: number): number | null {
  let remaining = offset;
  let result: number | null = null;
  doc.descendants((node, pos) => {
    if (result !== null) {
      return false;
    }
    // Non-text nodes must return true so descent continues into their children.
    if (!node.isText || !node.text) {
      return true;
    }
    const length = codepointLength(node.text);
    if (remaining <= length) {
      result = pos + codepointToUtf16(node.text, remaining);
      return false;
    }
    remaining -= length;
    return true;
  });
  if (result === null && remaining === 0) {
    return doc.content.size;
  }
  return result;
}

/**
 * Map ProseMirror positions back to code-point offsets over the document's
 * concatenated text (the inverse of codepointRangeToPm for text ranges).
 */
export function pmRangeToCodepoints(doc: ProseMirrorNode, from: number, to: number): CodepointRange {
  let codepointsBefore = 0;
  let start: number | null = null;
  let end: number | null = null;
  doc.descendants((node, pos) => {
    if (!node.isText || !node.text) {
      return true;
    }
    const nodeStart = pos;
    const nodeEnd = pos + node.nodeSize;
    const length = codepointLength(node.text);
    if (start === null && from <= nodeEnd) {
      start =
        from <= nodeStart
          ? codepointsBefore
          : codepointsBefore + utf16ToCodepoint(node.text, from - nodeStart);
    }
    if (end === null && to <= nodeEnd) {
      end =
        to <= nodeStart
          ? codepointsBefore
          : codepointsBefore + utf16ToCodepoint(node.text, to - nodeStart);
    }
    codepointsBefore += length;
    return start === null || end === null;
  });
  const total = codepointLength(doc.textContent);
  return { start: start ?? total, end: end ?? total };
}
