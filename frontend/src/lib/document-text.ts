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

export interface SentenceSpan {
  start: number; // code-point offset, inclusive
  end: number; // code-point offset, exclusive
  text: string;
  complete: boolean;
}

const ABBREVIATIONS = new Set([
  "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "fig",
  "no", "vol", "approx", "dept", "est", "min", "max", "eg", "ie", "al",
]);

const CLOSERS = new Set(["\"", "'", "\u201D", "\u2019", ")", "]", "}", "\u00BB"]);

// ADR-031: the model essay is Chinese; split on full-width terminators too.
// Chinese sentences need no following space (unlike English).
const CJK_TERMINATORS = new Set(["\u3002", "\uFF01", "\uFF1F"]); // 。！？
const CJK_CLOSERS = new Set([
  "\u300D", "\u300F", "\u201D", "\u2019", "\uFF09", "\u300B", "\u3011",
]); // 」』”’）》】

/**
 * Split text into sentence spans (code-point offsets), handling abbreviations,
 * decimals, initials, quoted sentences and paragraph breaks. A span is
 * `complete` when it ends with sentence punctuation (or a paragraph break);
 * trailing input without punctuation is incomplete and must not be checked
 * prematurely (user decision 2026-11-15 §5).
 */
export function splitSentences(text: string): SentenceSpan[] {
  const cps = Array.from(text);
  const spans: SentenceSpan[] = [];
  let start = 0;

  const push = (end: number, complete: boolean) => {
    const slice = cps.slice(start, end).join("");
    if (slice.trim() !== "") {
      spans.push({ start, end, text: slice, complete });
    }
    start = end;
  };

  for (let i = 0; i < cps.length; i += 1) {
    const ch = cps[i];
    if (ch === "\n" && cps[i + 1] === "\n") {
      push(i, true); // paragraph break: structurally complete
      i += 1;
      start = i + 1;
      continue;
    }
    if (CJK_TERMINATORS.has(ch)) {
      // ADR-031: Chinese sentence end — complete regardless of what follows.
      let end = i + 1;
      while (end < cps.length && CJK_TERMINATORS.has(cps[end])) {
        end += 1;
      }
      while (end < cps.length && CJK_CLOSERS.has(cps[end])) {
        end += 1;
      }
      push(end, true);
      i = end - 1;
      continue;
    }
    if (ch !== "." && ch !== "!" && ch !== "?") {
      continue;
    }
    if (ch === ".") {
      const prev = cps[i - 1];
      const next = cps[i + 1];
      if (prev >= "0" && prev <= "9" && next >= "0" && next <= "9") {
        continue; // decimal number
      }
      let wordStart = i - 1;
      while (wordStart >= start && /[A-Za-z]/.test(cps[wordStart])) {
        wordStart -= 1;
      }
      const word = cps.slice(wordStart + 1, i).join("").toLowerCase();
      if (ABBREVIATIONS.has(word)) {
        continue;
      }
      if (word.length === 1 && /[A-Z]/.test(cps[i - 1] ?? "")) {
        continue; // initial, e.g. "J. K. Rowling"
      }
    }
    let end = i + 1;
    while (end < cps.length && (cps[end] === "." || cps[end] === "!" || cps[end] === "?")) {
      end += 1;
    }
    while (end < cps.length && CLOSERS.has(cps[end])) {
      end += 1;
    }
    const after = cps[end];
    if (after === undefined || after === " " || after === "\t" || after === "\n") {
      // Quoted mid-sentence continuation: She said "Stop!" and left.
      const hadCloser = end > i + 1 && CLOSERS.has(cps[end - 1]);
      if (hadCloser) {
        let next = end;
        while (next < cps.length && (cps[next] === " " || cps[next] === "\t")) {
          next += 1;
        }
        const nextChar = cps[next];
        if (nextChar !== undefined && /[a-z]/.test(nextChar)) {
          continue; // lowercase continuation: the sentence is not finished
        }
      }
      push(end, true);
      while (start < cps.length && (cps[start] === " " || cps[start] === "\t")) {
        start += 1;
      }
      i = end - 1;
    }
  }
  if (start < cps.length) {
    push(cps.length, false);
  }
  return spans;
}
