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
