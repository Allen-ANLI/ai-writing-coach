import { Schema, type Node as ProseMirrorNode } from "@tiptap/pm/model";
import { describe, expect, it } from "vitest";

import {
  codepointLength,
  codepointRangeToPm,
  codepointToUtf16,
  pmRangeToCodepoints,
  utf16ToCodepoint,
} from "@/lib/text-positions";

const schema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: { content: "inline*", group: "block" },
    text: { group: "inline" },
  },
});

function doc(...paragraphs: string[]): ProseMirrorNode {
  return schema.node(
    "doc",
    null,
    paragraphs.map((text) =>
      schema.node("paragraph", null, text === "" ? [] : [schema.text(text)]),
    ),
  );
}

describe("codepoint / UTF-16 conversion", () => {
  it("counts astral characters once", () => {
    expect(codepointLength("a🎉b")).toBe(3);
    expect(codepointLength("中文")).toBe(2);
    expect(codepointLength("")).toBe(0);
  });

  it("converts codepoint offsets to UTF-16", () => {
    expect(codepointToUtf16("a🎉b", 0)).toBe(0);
    expect(codepointToUtf16("a🎉b", 1)).toBe(1);
    expect(codepointToUtf16("a🎉b", 2)).toBe(3);
    expect(codepointToUtf16("a🎉b", 3)).toBe(4);
    expect(codepointToUtf16("a🎉b", 99)).toBe(4);
  });

  it("converts UTF-16 offsets to codepoints", () => {
    expect(utf16ToCodepoint("a🎉b", 0)).toBe(0);
    expect(utf16ToCodepoint("a🎉b", 1)).toBe(1);
    expect(utf16ToCodepoint("a🎉b", 3)).toBe(2);
    expect(utf16ToCodepoint("a🎉b", 4)).toBe(3);
    expect(utf16ToCodepoint("a🎉b", 99)).toBe(3);
  });

  it("round-trips mixed emoji / CJK text", () => {
    const text = "Hello 🎉 中文 world 🚀!";
    for (let cp = 0; cp <= codepointLength(text); cp += 1) {
      expect(utf16ToCodepoint(text, codepointToUtf16(text, cp))).toBe(cp);
    }
  });
});

describe("ProseMirror position mapping", () => {
  it("maps a range inside one paragraph with an emoji", () => {
    const d = doc("Hello 🎉");
    // Text starts at PM position 1; emoji is codepoints 6..7, UTF-16 6..8.
    expect(codepointRangeToPm(d, 6, 7)).toEqual({ from: 7, to: 9 });
    expect(pmRangeToCodepoints(d, 7, 9)).toEqual({ start: 6, end: 7 });
  });

  it("maps ranges across paragraphs with CJK", () => {
    const d = doc("abc", "中文");
    // p1 text: PM 1..4 (3 codepoints). p2 text starts at PM 6 (2 codepoints).
    expect(codepointRangeToPm(d, 3, 5)).toEqual({ from: 4, to: 8 });
    expect(pmRangeToCodepoints(d, 4, 8)).toEqual({ start: 3, end: 5 });
  });

  it("handles the full document range", () => {
    const d = doc("a🎉", "b");
    const total = codepointLength(d.textContent);
    const range = codepointRangeToPm(d, 0, total);
    expect(range).not.toBeNull();
    expect(pmRangeToCodepoints(d, range!.from, range!.to)).toEqual({ start: 0, end: total });
  });

  it("maps zero-width range at document start", () => {
    const d = doc("abc");
    expect(codepointRangeToPm(d, 0, 0)).toEqual({ from: 1, to: 1 });
    expect(pmRangeToCodepoints(d, 0, 1)).toEqual({ start: 0, end: 0 });
  });

  it("rejects out-of-bounds ranges", () => {
    const d = doc("abc");
    expect(codepointRangeToPm(d, 0, 4)).toBeNull();
    expect(codepointRangeToPm(d, -1, 2)).toBeNull();
    expect(codepointRangeToPm(d, 2, 1)).toBeNull();
  });

  it("round-trips every offset in a mixed document", () => {
    const d = doc("One 🎉 two", "中文 three 🚀", "plain");
    const total = codepointLength(d.textContent);
    for (let cp = 0; cp <= total; cp += 1) {
      const range = codepointRangeToPm(d, cp, cp);
      expect(range).not.toBeNull();
      expect(pmRangeToCodepoints(d, range!.from, range!.to)).toEqual({ start: cp, end: cp });
    }
  });
});
