"use client";

/**
 * Left outline (finalized UX, user decision 2026-11-15 §2.2): a collapsible
 * hierarchical TEXT list — essay sections (headings), paragraphs, and
 * sentence-level ideas. Not a chart/diagram. Synchronized with the document;
 * clicking an item moves the caret there. Expanded by default.
 */

import { useEffect, useMemo, useState } from "react";
import type { Editor } from "@tiptap/react";
import { useQuery } from "@tanstack/react-query";

import { splitSentences } from "@/lib/document-text";
import { getOutline, listOutlines } from "@/services/outlines";
import type { OutlineNodeData } from "@/types/api";

interface OutlineNode {
  id: string;
  label: string;
  pos: number;
  children: OutlineNode[];
}

function truncate(text: string, max: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max)}…` : clean;
}

function buildOutline(editor: Editor): OutlineNode[] {
  const sections: OutlineNode[] = [];
  let current: OutlineNode | null = null;

  const ensureSection = (pos: number): OutlineNode => {
    if (!current) {
      current = { id: `s-${pos}`, label: "Untitled section", pos, children: [] };
      sections.push(current);
    }
    return current;
  };

  editor.state.doc.forEach((node, pos) => {
    if (node.type.name === "heading") {
      current = {
        id: `h-${pos}`,
        label: truncate(node.textContent, 60) || "Untitled heading",
        pos,
        children: [],
      };
      sections.push(current);
      return;
    }
    const text = node.textContent;
    if (text.trim() === "") {
      return;
    }
    const section = ensureSection(pos);
    const paragraph: OutlineNode = {
      id: `p-${pos}`,
      label: truncate(text, 48) || "Paragraph",
      pos,
      children: [],
    };
    const spans = splitSentences(text);
    for (const span of spans) {
      if (span.text.trim() === "") {
        continue;
      }
      paragraph.children.push({
        id: `sent-${pos}-${span.start}`,
        label: truncate(span.text, 56),
        // +1: paragraph content starts one position inside the node.
        pos: pos + 1 + span.start,
        children: [],
      });
    }
    section.children.push(paragraph);
  });

  return sections;
}

function OutlineItem({
  node,
  depth,
  collapsed,
  onToggle,
  onNavigate,
}: {
  node: OutlineNode;
  depth: number;
  collapsed: Set<string>;
  onToggle: (id: string) => void;
  onNavigate: (pos: number) => void;
}) {
  const isCollapsed = collapsed.has(node.id);
  const hasChildren = node.children.length > 0;
  return (
    <li>
      <div
        className="group flex items-center gap-1 rounded px-1 py-0.5 hover:bg-zinc-100 dark:hover:bg-zinc-800"
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            aria-label={isCollapsed ? `Expand ${node.label}` : `Collapse ${node.label}`}
            aria-expanded={!isCollapsed}
            onClick={() => onToggle(node.id)}
            className="flex h-4 w-4 shrink-0 items-center justify-center text-[9px] text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
          >
            {isCollapsed ? "▸" : "▾"}
          </button>
        ) : (
          <span className="h-4 w-4 shrink-0" />
        )}
        <button
          type="button"
          onClick={() => onNavigate(node.pos)}
          className={`min-w-0 flex-1 truncate text-left ${
            depth === 0
              ? "text-sm font-medium text-zinc-900 dark:text-zinc-100"
              : depth === 1
                ? "text-xs text-zinc-600 dark:text-zinc-400"
                : "text-xs text-zinc-500 dark:text-zinc-500"
          }`}
          title={node.label}
        >
          {node.label}
        </button>
      </div>
      {hasChildren && !isCollapsed && (
        <ul>
          {node.children.map((child) => (
            <OutlineItem
              key={child.id}
              node={child}
              depth={depth + 1}
              collapsed={collapsed}
              onToggle={onToggle}
              onNavigate={onNavigate}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function PlanBranch({ nodes, parentId }: { nodes: OutlineNodeData[]; parentId: string | null }) {
  const children = nodes
    .filter((node) => node.parent_id === parentId)
    .sort((a, b) => a.sort_order - b.sort_order);
  if (children.length === 0) {
    return null;
  }
  return (
    <ul className={parentId !== null ? "ml-3 border-l border-zinc-100 pl-2 dark:border-zinc-800" : "mt-2"}>
      {children.map((node) => (
        <li key={node.id} className="mt-1">
          <p
            className={
              node.node_type === "section"
                ? "text-xs font-medium text-zinc-800 dark:text-zinc-200"
                : node.node_type === "paragraph"
                  ? "text-xs text-zinc-600 dark:text-zinc-400"
                  : "text-xs text-zinc-500 dark:text-zinc-500"
            }
            title={node.title}
          >
            {node.node_type === "sentence_idea" ? "· " : ""}
            {node.title}
          </p>
          <PlanBranch nodes={nodes} parentId={node.id} />
        </li>
      ))}
    </ul>
  );
}

export function OutlinePanel({
  editor,
  essayId,
  essayTitle,
  writingTypeLabel,
}: {
  editor: Editor | null;
  essayId: string;
  essayTitle: string;
  writingTypeLabel: string;
}) {
  const [version, setVersion] = useState(0);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const outlinesQuery = useQuery({
    queryKey: ["outlines", essayId],
    queryFn: async () => (await listOutlines(essayId)).data.items,
  });
  const confirmedPlan = outlinesQuery.data?.find((item) => item.status === "confirmed") ?? null;
  const planQuery = useQuery({
    queryKey: ["outline", confirmedPlan?.id],
    queryFn: async () => (await getOutline(confirmedPlan?.id as string)).data,
    enabled: confirmedPlan !== null,
  });
  const planNodes = planQuery.data?.nodes ?? [];

  useEffect(() => {
    if (!editor) {
      return;
    }
    const update = () => setVersion((value) => value + 1);
    editor.on("update", update);
    editor.on("create", update);
    return () => {
      editor.off("update", update);
      editor.off("create", update);
    };
  }, [editor]);

  const outline = useMemo(() => {
    if (!editor) {
      return [];
    }
    void version; // rebuild on document changes
    return buildOutline(editor);
  }, [editor, version]);

  const onToggle = (id: string) => {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const onNavigate = (pos: number) => {
    editor?.chain().focus().setTextSelection(pos).scrollIntoView().run();
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <section aria-label="Essay prompt">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
          Essay
        </h2>
        <p className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-100">{essayTitle}</p>
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{writingTypeLabel}</p>
      </section>

      {confirmedPlan && (
        <section aria-label="Confirmed writing plan" data-testid="confirmed-plan">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
            Writing plan
          </h2>
          {confirmedPlan.thesis_statement && (
            <p className="mt-1 text-xs italic text-zinc-600 dark:text-zinc-400">
              {confirmedPlan.thesis_statement}
            </p>
          )}
          <PlanBranch nodes={planNodes} parentId={null} />
        </section>
      )}

      <section aria-label="Document outline" className="flex-1" data-testid="outline-tree">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
          Outline
        </h2>
        {outline.length === 0 ? (
          <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">
            Start writing — sections, paragraphs and sentence ideas appear here.
          </p>
        ) : (
          <ul className="mt-2">
            {outline.map((node) => (
              <OutlineItem
                key={node.id}
                node={node}
                depth={0}
                collapsed={collapsed}
                onToggle={onToggle}
                onNavigate={onNavigate}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
