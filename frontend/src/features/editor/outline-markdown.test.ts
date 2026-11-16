import { describe, expect, it } from "vitest";

import { parseOutlineMarkdown } from "./outline-markdown";

describe("parseOutlineMarkdown (ADR-032/033)", () => {
  it("parses sections, paragraphs and bullets hierarchically", () => {
    const md = "## 引言\n### 背景与立场\n- 1. 城市交通拥堵\n- 2. 主张免费\n## 结论";
    const blocks = parseOutlineMarkdown(md);
    expect(blocks).toEqual([
      { type: "section", text: "引言" },
      { type: "paragraph", text: "背景与立场" },
      { type: "bullet", depth: 0, text: "1. 城市交通拥堵" },
      { type: "bullet", depth: 0, text: "2. 主张免费" },
      { type: "section", text: "结论" },
    ]);
  });

  it("captures nested bullet depth from indentation (ADR-033)", () => {
    const md = "- **原因1：节奏快**：忙碌无暇交往。例如：早出晚归。\n  - 工时长\n  - 通勤累";
    const blocks = parseOutlineMarkdown(md);
    expect(blocks).toEqual([
      { type: "bullet", depth: 0, text: "**原因1：节奏快**：忙碌无暇交往。例如：早出晚归。" },
      { type: "bullet", depth: 1, text: "工时长" },
      { type: "bullet", depth: 1, text: "通勤累" },
    ]);
  });

  it("parses ordered-list idea markers with their number (ADR-034)", () => {
    const md =
      "## 原因分析\n### 两大原因\n" +
      "1. **生活节奏快**：忙碌无暇交往。例如：早出晚归。\n" +
      "   1. 工时长\n   2. 通勤累\n" +
      "2. **缺共享空间**：物理环境阻碍相聚。";
    const blocks = parseOutlineMarkdown(md);
    expect(blocks).toEqual([
      { type: "section", text: "原因分析" },
      { type: "paragraph", text: "两大原因" },
      { type: "ordered", depth: 0, number: 1, text: "**生活节奏快**：忙碌无暇交往。例如：早出晚归。" },
      { type: "ordered", depth: 1, number: 1, text: "工时长" },
      { type: "ordered", depth: 1, number: 2, text: "通勤累" },
      { type: "ordered", depth: 0, number: 2, text: "**缺共享空间**：物理环境阻碍相聚。" },
    ]);
  });

  it("keeps a bullet whose text starts with a number as a bullet (ADR-034)", () => {
    const blocks = parseOutlineMarkdown("- 1. 城市交通拥堵");
    expect(blocks).toEqual([{ type: "bullet", depth: 0, text: "1. 城市交通拥堵" }]);
  });

  it("ignores blank lines and treats # as a section", () => {
    const blocks = parseOutlineMarkdown("# 标题\n\n普通文本\n* 项目");
    expect(blocks).toEqual([
      { type: "section", text: "标题" },
      { type: "text", text: "普通文本" },
      { type: "bullet", depth: 0, text: "项目" },
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