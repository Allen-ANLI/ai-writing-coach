import { describe, expect, it } from "vitest";

import { wordDiff } from "./word-diff";

describe("wordDiff", () => {
  it("marks only the replaced words", () => {
    const segments = wordDiff("very like", "really like");
    expect(segments).toEqual([
      { text: "really ", changed: true },
      { text: "like", changed: false },
    ]);
  });

  it("keeps unchanged context in normal color", () => {
    const segments = wordDiff("go to school", "went to school");
    expect(segments).toEqual([
      { text: "went ", changed: true },
      { text: "to school", changed: false },
    ]);
  });

  it("identical text has no changed segments", () => {
    expect(wordDiff("a b", "a b")).toEqual([{ text: "a b", changed: false }]);
  });

  it("empty original marks everything changed", () => {
    expect(wordDiff("", "a b")).toEqual([{ text: "a b", changed: true }]);
  });

  it("handles inserted words", () => {
    const segments = wordDiff("like books", "like reading books");
    expect(segments).toEqual([
      { text: "like ", changed: false },
      { text: "reading ", changed: true },
      { text: "books", changed: false },
    ]);
  });

  it("concatenated segments reproduce the replacement exactly (ADR-028)", () => {
    const cases: Array<[string, string]> = [
      ["very like", "really like"],
      ["go to school", "went to school"],
      ["like books", "like reading books"],
      ["very like", "am very fond of"],
      ["a b", "a b"],
      ["", "a b"],
      ["get more experience", "gain hands-on experience"],
    ];
    for (const [original, replacement] of cases) {
      const joined = wordDiff(original, replacement)
        .map((segment) => segment.text)
        .join("");
      expect(joined).toBe(replacement);
    }
  });

  it("preserves multiple spaces and leading whitespace", () => {
    expect(wordDiff("a b", "a  b").map((s) => s.text).join("")).toBe("a  b");
    expect(wordDiff("a", " a").map((s) => s.text).join("")).toBe(" a");
  });
});