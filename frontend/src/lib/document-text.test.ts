import { describe, expect, it } from "vitest";

import { countWords } from "@/lib/document-text";

describe("countWords (mirrors backend tiptap.count_words)", () => {
  it("counts whitespace-separated tokens", () => {
    expect(countWords("Hello world.")).toBe(2);
    expect(countWords("  one\ttwo\n\nthree  ")).toBe(3);
    expect(countWords("")).toBe(0);
    expect(countWords("   \n\t ")).toBe(0);
  });

  it("treats emoji and CJK runs as single tokens like the server", () => {
    expect(countWords("Emoji 🎉 and 中文 stay exact.")).toBe(6);
    expect(countWords("提高公众环保意识")).toBe(1);
  });
});
