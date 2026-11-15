import { describe, expect, it } from "vitest";

import { wordDiff } from "./word-diff";

describe("wordDiff", () => {
  it("marks only the replaced words", () => {
    const segments = wordDiff("very like", "really like");
    expect(segments).toEqual([
      { text: "really", changed: true },
      { text: "like", changed: false },
    ]);
  });

  it("keeps unchanged context in normal color", () => {
    const segments = wordDiff("go to school", "went to school");
    expect(segments).toEqual([
      { text: "went", changed: true },
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
      { text: "like", changed: false },
      { text: "reading", changed: true },
      { text: "books", changed: false },
    ]);
  });
});
