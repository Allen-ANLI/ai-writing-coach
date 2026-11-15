import { describe, expect, it } from "vitest";

import { countWords, splitSentences } from "@/lib/document-text";

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

describe("splitSentences (sentence-completion detection)", () => {
  it("splits simple sentences and marks them complete", () => {
    const spans = splitSentences("He go to school. She likes apples.");
    expect(spans).toHaveLength(2);
    expect(spans[0].text).toBe("He go to school.");
    expect(spans[0].complete).toBe(true);
    expect(spans[1].text).toBe("She likes apples.");
    expect(spans[1].start).toBe(17);
  });

  it("marks trailing input without punctuation incomplete", () => {
    const spans = splitSentences("He go to school");
    expect(spans).toHaveLength(1);
    expect(spans[0].complete).toBe(false);
  });

  it("does not split decimals", () => {
    const spans = splitSentences("The value is 3.14 exactly.");
    expect(spans).toHaveLength(1);
    expect(spans[0].text).toBe("The value is 3.14 exactly.");
  });

  it("does not split abbreviations", () => {
    const spans = splitSentences("Mr. Smith went home. He was tired.");
    expect(spans).toHaveLength(2);
    expect(spans[0].text).toBe("Mr. Smith went home.");
  });

  it("does not split initials", () => {
    const spans = splitSentences("J. K. Rowling wrote books.");
    expect(spans).toHaveLength(1);
  });

  it("keeps quoted sentence endings together", () => {
    const spans = splitSentences('She said "Stop!" and left.');
    expect(spans).toHaveLength(1);
    expect(spans[0].text).toBe('She said "Stop!" and left.');
  });

  it("treats paragraph breaks as completion boundaries", () => {
    const spans = splitSentences("First idea\n\nSecond idea");
    expect(spans).toHaveLength(2);
    expect(spans[0].complete).toBe(true);
    expect(spans[1].complete).toBe(false);
  });

  it("handles emoji offsets in code points", () => {
    const spans = splitSentences("🎉 Party time. Next sentence.");
    expect(spans[0].text).toBe("🎉 Party time.");
    expect(spans[1].start).toBe(14);
  });

  it("handles multiple punctuation marks", () => {
    const spans = splitSentences("Really?! Yes. Okay.");
    expect(spans).toHaveLength(3);
    expect(spans[0].text).toBe("Really?!");
  });
});
