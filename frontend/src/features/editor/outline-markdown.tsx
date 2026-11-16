"use client";

/**
 * 轻量 Markdown 大纲渲染（ADR-032，无第三方依赖）。
 * 大纲是受控格式：## 章节、### 段落、-  bullet（可带 1. 2. 编号）、**加粗**。
 * 解析为结构化块再渲染，层级清晰、留白充足，便于扫读。
 */

export type OutlineBlock =
  | { type: "section"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "bullet"; text: string }
  | { type: "text"; text: string };

export function parseOutlineMarkdown(md: string): OutlineBlock[] {
  const blocks: OutlineBlock[] = [];
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trim();
    if (line === "") {
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push({ type: "paragraph", text: line.slice(4).trim() });
    } else if (line.startsWith("## ")) {
      blocks.push({ type: "section", text: line.slice(3).trim() });
    } else if (line.startsWith("# ")) {
      blocks.push({ type: "section", text: line.slice(2).trim() });
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      blocks.push({ type: "bullet", text: line.slice(2).trim() });
    } else {
      blocks.push({ type: "text", text: line });
    }
  }
  return blocks;
}

/** Render **bold** spans inside a line; the rest is plain text. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <strong key={index} className="font-semibold text-zinc-800 dark:text-zinc-100">
            {part}
          </strong>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

export function OutlineMarkdown({ md }: { md: string }) {
  const blocks = parseOutlineMarkdown(md);
  return (
    <div className="space-y-2" data-testid="outline-markdown">
      {blocks.map((block, index) => {
        if (block.type === "section") {
          return (
            <h4
              key={index}
              className="mt-1 border-l-2 border-sky-400 pl-2 text-xs font-semibold text-zinc-800 dark:text-zinc-100"
            >
              <Inline text={block.text} />
            </h4>
          );
        }
        if (block.type === "paragraph") {
          return (
            <h5
              key={index}
              className="pl-2 text-[11px] font-medium text-zinc-600 dark:text-zinc-300"
            >
              <Inline text={block.text} />
            </h5>
          );
        }
        if (block.type === "bullet") {
          return (
            <div
              key={index}
              className="flex gap-1.5 pl-4 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400"
            >
              <span aria-hidden="true" className="text-sky-400">
                •
              </span>
              <span>
                <Inline text={block.text} />
              </span>
            </div>
          );
        }
        return (
          <p key={index} className="pl-2 text-[11px] text-zinc-500 dark:text-zinc-400">
            <Inline text={block.text} />
          </p>
        );
      })}
    </div>
  );
}