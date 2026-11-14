/**
 * Client-side document text rules. These MUST mirror the backend derivation
 * (backend/app/modules/essays/tiptap.py): blocks joined with "\n\n", words are
 * whitespace-separated tokens. The server re-derives and validates anyway.
 */

export const BLOCK_SEPARATOR = "\n\n";

export function countWords(text: string): number {
  const matches = text.match(/\S+/g);
  return matches ? matches.length : 0;
}

/**
 * Sentence containing a code-point offset (mirrors the backend's
 * _sentence_around). Returns [sentence, startCodepoint].
 */
export function sentenceAround(text: string, offset: number): [string, number] {
  const clamped = Math.max(0, Math.min(offset, Math.max(0, text.length - 1)));
  let start = clamped;
  while (start > 0 && !".!?\n".includes(text[start - 1])) {
    start -= 1;
  }
  while (start < text.length && (text[start] === " " || text[start] === "\t")) {
    start += 1;
  }
  let end = clamped;
  while (end < text.length && !".!?\n".includes(text[end])) {
    end += 1;
  }
  if (end < text.length) {
    end += 1;
  }
  return [text.slice(start, end), start];
}
