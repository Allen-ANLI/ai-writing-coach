import { describe, expect, it } from "vitest";

import { parseOutlineMarkdown } from "./outline-markdown";

describe("parseOutlineMarkdown (ADR-032)", () => {
  it("parses sections, paragraphs and bullets hierarchically", () => {
    const md = "## 引言\n### 背景与立场\n- 1. 城市交通拥堵\n- 2. 主张免费\n## 结论\n## 重申";
    const blocks = parseOutlineMarkdown(md);
    expect(blocks).toEqual([
      { type: "section", text: "引言" },
      { type: "paragraph", text: "背景与立场" },
      { type: "bullet", text: "1. 城市交通拥堵" },
      { type: "bullet", text: "2. 主张免费" },
      { type: "section", text: "结论" },
      { type: "section", text: "重申" },
    ]);
  });

  it("ignores blank lines and treats # as a section", () => {
    const blocks = parseOutlineMarkdown("# 标题\n\n普通文本\n* 项目");
    expect(blocks).toEqual([
      { type: "section", text: "标题" },
      { type: "text", text: "普通文本" },
      { type: "bullet", text: "项目" },
    ]);
  });

  it("keeps bold markers in text for inline rendering", () => {
    const blocks = parseOutlineMarkdown("## **重点**章节");
    expect(blocks[0]).toEqual({ type: "section", text: "**重点**章节" });
  });

  it("returns empty for empty input", () => {
    expect(parseOutlineMarkdown("")).toEqual([]);
    expect(parseOutlineMarkdown("  \n\n ")).toEqual([]);
  });
});