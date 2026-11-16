"use client";

/**
 * 轻量 Markdown 大纲渲染（ADR-032/033/034，无第三方依赖）。
 * 受控格式：## 章节、### 段落、有序列表 1. 要点（可缩进表层级）、
 * - bullet（向后兼容旧大纲）、**加粗概括**。
 * 始终展开的嵌套缩进：要点先几个字粗体概括，再详解/举例，子要点更深缩进。
 */

export type OutlineBlock =
  | { type: "section"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "bullet"; depth: number; text: string }
  | { type: "ordered"; depth: number; number: number; text: string }
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
    } else if (/^\d+\.\s/.test(line)) {
      // ADR-034: ordered-list idea markers ("1. **短概括**：…"); the number
      // comes from the marker, not an embedded "原因1" label.
      const leading = raw.length - raw.trimStart().length;
      const marker = /^(\d+)\.\s+(.*)$/.exec(line);
      blocks.push({
        type: "ordered",
        depth: Math.floor(leading / 2),
        number: marker ? Number(marker[1]) : 1,
        text: marker ? marker[2].trim() : line,
      });
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      const leading = raw.length - raw.trimStart().length;
      blocks.push({
        type: "bullet",
        depth: Math.floor(leading / 2),
        text: line.slice(2).trim(),
      });
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
    <div className="space-y-1.5" data-testid="outline-markdown">
      {blocks.map((block, index) => {
        if (block.type === "section") {
          return (
            <h4
              key={index}
              className="mt-2 border-l-2 border-sky-400 pl-2 text-xs font-semibold text-zinc-800 first:mt-0 dark:text-zinc-100"
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
        if (block.type === "ordered") {
          return (
            <div
              key={index}
              className="flex gap-1.5 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400"
              style={{ paddingLeft: `${16 + block.depth * 16}px` }}
            >
              <span
                aria-hidden="true"
                className={
                  block.depth > 0
                    ? "shrink-0 text-zinc-300 dark:text-zinc-600"
                    : "shrink-0 font-medium text-sky-500"
                }
              >
                {block.number}.
              </span>
              <span>
                <Inline text={block.text} />
              </span>
            </div>
          );
        }
        if (block.type === "bullet") {
          return (
            <div
              key={index}
              className="flex gap-1.5 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400"
              style={{ paddingLeft: `${16 + block.depth * 16}px` }}
            >
              <span
                aria-hidden="true"
                className={block.depth > 0 ? "text-zinc-300 dark:text-zinc-600" : "text-sky-400"}
              >
                {block.depth > 0 ? "◦" : "•"}
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