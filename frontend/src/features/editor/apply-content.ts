/**
 * Apply server-returned content with a minimal diff (ADR-027).
 *
 * A full setContent replaces the whole document: ProseMirror maps every
 * decoration position into the replaced range, so ALL grammar/polish
 * highlights collapse after each acceptance. Replacing only the changed
 * range lets surviving decorations (and the caret) map through the
 * transaction untouched.
 *
 * The diff helpers mirror ProseMirror's internal findDiffStart/findDiffEnd
 * algorithm (not exported by the installed prosemirror packages).
 */

import type { Editor } from "@tiptap/react";
import { Fragment, Node as ProseMirrorNode, type Slice } from "@tiptap/pm/model";

import type { TipTapDocument } from "@/types/api";

export interface ContentDiff {
  from: number;
  to: number;
  slice: Slice;
}

function findDiffStart(a: Fragment, b: Fragment, pos = 0): number | null {
  for (let i = 0; ; i += 1) {
    if (i === a.childCount || i === b.childCount) {
      return a.childCount === b.childCount ? null : pos;
    }
    const childA = a.child(i);
    const childB = b.child(i);
    if (childA === childB) {
      pos += childA.nodeSize;
      continue;
    }
    if (!childA.sameMarkup(childB)) {
      return pos;
    }
    if (childA.isText && childA.text !== childB.text) {
      const textA = childA.text ?? "";
      const textB = childB.text ?? "";
      let j = 0;
      while (textA[j] === textB[j]) {
        j += 1;
        pos += 1;
      }
      return pos;
    }
    if (childA.content.size || childB.content.size) {
      const inner = findDiffStart(childA.content, childB.content, pos + 1);
      if (inner !== null) {
        return inner;
      }
    }
    pos += childA.nodeSize;
  }
}

function findDiffEnd(
  a: Fragment,
  b: Fragment,
  posA = a.size,
  posB = b.size,
): { a: number; b: number } | null {
  for (let iA = a.childCount, iB = b.childCount; ; iA -= 1, iB -= 1) {
    if (iA === 0 || iB === 0) {
      return iA === iB ? null : { a: posA, b: posB };
    }
    const childA = a.child(iA - 1);
    const childB = b.child(iB - 1);
    if (childA === childB) {
      posA -= childA.nodeSize;
      posB -= childB.nodeSize;
      continue;
    }
    if (!childA.sameMarkup(childB)) {
      return { a: posA, b: posB };
    }
    if (childA.isText && childA.text !== childB.text) {
      const textA = childA.text ?? "";
      const textB = childB.text ?? "";
      let same = 0;
      const minSize = Math.min(textA.length, textB.length);
      while (same < minSize && textA[textA.length - same - 1] === textB[textB.length - same - 1]) {
        same += 1;
      }
      return { a: posA - same, b: posB - same };
    }
    if (childA.content.size || childB.content.size) {
      const inner = findDiffEnd(childA.content, childB.content, posA - 1, posB - 1);
      if (inner !== null) {
        return inner;
      }
    }
    posA -= childA.nodeSize;
    posB -= childB.nodeSize;
  }
}

export function computeContentDiff(
  oldDoc: ProseMirrorNode,
  newDoc: ProseMirrorNode,
): ContentDiff | null {
  const start = findDiffStart(oldDoc.content, newDoc.content);
  if (start === null) {
    return null; // identical documents: nothing to apply
  }
  const end = findDiffEnd(oldDoc.content, newDoc.content) ?? {
    a: oldDoc.content.size,
    b: newDoc.content.size,
  };
  return {
    from: Math.min(start, end.a),
    to: Math.max(start, end.a),
    slice: newDoc.slice(Math.min(start, end.b), Math.max(start, end.b)),
  };
}

export function applyServerContent(editor: Editor, content: TipTapDocument): void {
  const newDoc = ProseMirrorNode.fromJSON(editor.schema, content);
  const diff = computeContentDiff(editor.state.doc, newDoc);
  if (!diff) {
    return;
  }
  editor.view.dispatch(editor.state.tr.replaceWith(diff.from, diff.to, diff.slice.content));
}