"use client";

/**
 * Collapsible left outline (confirmed layout: expanded by default).
 * Shows the essay prompt area and live document headings; clicking a heading
 * moves the caret there. On narrow screens the parent renders it as an overlay.
 */

import { useEffect, useState } from "react";
import type { Editor } from "@tiptap/react";

interface HeadingItem {
  level: number;
  text: string;
  pos: number;
}

function collectHeadings(editor: Editor): HeadingItem[] {
  const headings: HeadingItem[] = [];
  editor.state.doc.descendants((node, pos) => {
    if (node.type.name === "heading") {
      headings.push({
        level: typeof node.attrs.level === "number" ? node.attrs.level : 1,
        text: node.textContent || "Untitled heading",
        pos,
      });
    }
    return true;
  });
  return headings;
}

export function OutlinePanel({
  editor,
  essayTitle,
  writingTypeLabel,
}: {
  editor: Editor | null;
  essayTitle: string;
  writingTypeLabel: string;
}) {
  const [headings, setHeadings] = useState<HeadingItem[]>([]);

  useEffect(() => {
    if (!editor) {
      return;
    }
    const update = () => setHeadings(collectHeadings(editor));
    update();
    editor.on("update", update);
    editor.on("create", update);
    return () => {
      editor.off("update", update);
      editor.off("create", update);
    };
  }, [editor]);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <section aria-label="Essay prompt">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
          Essay
        </h2>
        <p className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-100">{essayTitle}</p>
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{writingTypeLabel}</p>
      </section>

      <section aria-label="Document outline" className="flex-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
          Outline
        </h2>
        {headings.length === 0 ? (
          <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">
            Add headings (H1/H2) to build your outline.
          </p>
        ) : (
          <ul className="mt-2 space-y-1">
            {headings.map((heading, index) => (
              <li key={`${heading.pos}-${index}`}>
                <button
                  type="button"
                  onClick={() => {
                    editor?.chain().focus().setTextSelection(heading.pos + 1).scrollIntoView().run();
                  }}
                  className={`w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                    heading.level === 1
                      ? "font-medium text-zinc-900 dark:text-zinc-100"
                      : "pl-5 text-zinc-600 dark:text-zinc-400"
                  }`}
                >
                  {heading.text}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
