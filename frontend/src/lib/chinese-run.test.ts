import { describe, expect, it } from "vitest";

import { containsChinese, findChineseRunAt } from "./chinese-run";

describe("findChineseRunAt", () => {
  it("finds the run ending at the caret", () => {
    const text = "I think 提高公众环保意识 is important.";
    const caret = "I think 提高公众环保意识".length;
    expect(findChineseRunAt(text, caret)).toEqual({
      start: 8,
      end: 16,
      text: "提高公众环保意识",
    });
  });

  it("extends across the whole run when the caret sits inside it", () => {
    const text = "提高公众环保意识";
    expect(findChineseRunAt(text, 4)).toEqual({ start: 0, end: 8, text });
  });

  it("detects a run when the caret is right before it", () => {
    expect(findChineseRunAt("你好 world", 0)).toEqual({ start: 0, end: 2, text: "你好" });
  });

  it("includes Chinese punctuation inside the run", () => {
    const text = "他说，你好。然后离开";
    expect(findChineseRunAt(text, text.length)?.text).toBe("他说，你好。然后离开");
  });

  it("returns null for English-only text", () => {
    expect(findChineseRunAt("I like apples.", 5)).toBeNull();
  });

  it("returns null when the caret is away from any run", () => {
    expect(findChineseRunAt("你好 world", 8)).toBeNull();
  });

  it("returns null for empty text", () => {
    expect(findChineseRunAt("", 0)).toBeNull();
  });

  it("stops at English boundaries", () => {
    const text = "very 喜欢 this book";
    expect(findChineseRunAt(text, 7)).toEqual({ start: 5, end: 7, text: "喜欢" });
  });
});

describe("containsChinese", () => {
  it("detects CJK ideographs", () => {
    expect(containsChinese("提高")).toBe(true);
    expect(containsChinese("hello")).toBe(false);
  });
});