/**
 * Chinese-run detection for the inline translation assist (ADR-027).
 * Works in UTF-16 offsets inside a single text block; CJK ideographs are
 * single-unit, so block-relative offsets map 1:1 to ProseMirror positions.
 */

const RUN_CHAR =
  /[\u4e00-\u9fff\u3400-\u4dbf\u3001\u3002\uff0c\uff1b\uff1a\uff1f\uff01\u201c\u201d\u2018\u2019\uff08\uff09\u300a\u300b]/;

export interface ChineseRun {
  start: number;
  end: number;
  text: string;
}

/**
 * Maximal Chinese run touching the caret: the character before the caret,
 * or (when the caret sits right before a run) the character at the caret.
 */
export function findChineseRunAt(text: string, caret: number): ChineseRun | null {
  if (text.length === 0) {
    return null;
  }
  const clamped = Math.min(Math.max(caret, 0), text.length);
  let idx = clamped - 1;
  if (idx < 0 || !RUN_CHAR.test(text[idx])) {
    if (clamped < text.length && RUN_CHAR.test(text[clamped])) {
      idx = clamped;
    } else {
      return null;
    }
  }
  let start = idx;
  while (start > 0 && RUN_CHAR.test(text[start - 1])) {
    start -= 1;
  }
  let end = idx + 1;
  while (end < text.length && RUN_CHAR.test(text[end])) {
    end += 1;
  }
  return { start, end, text: text.slice(start, end) };
}

export function containsChinese(text: string): boolean {
  return /[\u4e00-\u9fff\u3400-\u4dbf]/.test(text);
}