/**
 * Grammar feedback extension (finalized UX, user decision 2026-11-15 §2).
 *
 * - Inline decorations underline issue ranges (color by category). No
 *   always-visible hint blocks: feedback floats on hover (React layer).
 * - Hover events are bridged via DOM CustomEvents; the React layer subscribes
 *   in effects (render-phase pure).
 * - Decorations are never part of the persisted document or word count.
 * - Issue ranges map through transactions; unreliable mappings are dropped.
 */

import { Extension } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";

import type { IssueData, RevealedSuggestion } from "@/types/api";

export interface GrammarIssueState {
  issue: IssueData;
  from: number;
  to: number;
  revealed: RevealedSuggestion[] | null;
}

interface GrammarPluginState {
  issues: GrammarIssueState[];
}

export const GRAMMAR_EVENTS = {
  reveal: "awc-grammar:reveal",
  ignore: "awc-grammar:ignore",
  teach: "awc-grammar:teach",
  hover: "awc-grammar:hover",
  hoverEnd: "awc-grammar:hover-end",
} as const;

function emit(name: string, detail: Record<string, unknown>) {
  document.dispatchEvent(new CustomEvent(name, { detail }));
}

export const grammarPluginKey = new PluginKey<GrammarPluginState>("awcGrammar");

export type GrammarMeta =
  | { type: "set"; issues: GrammarIssueState[] }
  | { type: "reveal"; issueId: string; suggestions: RevealedSuggestion[] }
  | { type: "remove"; issueId: string }
  | { type: "update"; issueId: string; state: GrammarIssueState };

function buildDecorations(doc: ProseMirrorNode, issues: GrammarIssueState[]): DecorationSet {
  const decorations: Decoration[] = [];
  const docSize = doc.content.size;
  for (const item of issues) {
    if (item.from < 0 || item.to > docSize || item.from >= item.to) {
      continue;
    }
    decorations.push(
      Decoration.inline(item.from, item.to, {
        class: `awc-issue awc-issue--${item.issue.category}`,
        "data-issue-id": item.issue.id,
      }),
    );
  }
  return DecorationSet.create(doc, decorations);
}

export function createGrammarExtension() {
  return Extension.create({
    name: "awcGrammar",

    addProseMirrorPlugins() {
      return [
        new Plugin<GrammarPluginState>({
          key: grammarPluginKey,
          state: {
            init: () => ({ issues: [] }),
            apply(tr, previous) {
              let issues = previous.issues;
              if (tr.docChanged) {
                issues = issues
                  .map((item) => ({
                    ...item,
                    from: tr.mapping.map(item.from),
                    to: tr.mapping.map(item.to, 1),
                  }))
                  .filter((item) => item.from < item.to);
              }
              const meta = tr.getMeta(grammarPluginKey) as GrammarMeta | undefined;
              if (meta) {
                switch (meta.type) {
                  case "set":
                    issues = meta.issues;
                    break;
                  case "reveal":
                    issues = issues.map((item) =>
                      item.issue.id === meta.issueId
                        ? { ...item, revealed: meta.suggestions }
                        : item,
                    );
                    break;
                  case "remove":
                    issues = issues.filter((item) => item.issue.id !== meta.issueId);
                    break;
                  case "update":
                    issues = issues.map((item) =>
                      item.issue.id === meta.issueId ? meta.state : item,
                    );
                    break;
                }
              }
              return { issues };
            },
          },
          props: {
            decorations(state) {
              const pluginState = grammarPluginKey.getState(state);
              if (!pluginState || pluginState.issues.length === 0) {
                return DecorationSet.empty;
              }
              return buildDecorations(state.doc, pluginState.issues);
            },
            handleDOMEvents: {
              mouseover(view, event) {
                const target = (event.target as HTMLElement | null)?.closest?.(".awc-issue");
                const issueId = target?.getAttribute("data-issue-id");
                if (issueId) {
                  const rect = (target as HTMLElement).getBoundingClientRect();
                  emit(GRAMMAR_EVENTS.hover, {
                    issueId,
                    top: rect.bottom,
                    left: rect.left,
                  });
                }
                return false;
              },
              mouseout(view, event) {
                const target = (event.target as HTMLElement | null)?.closest?.(".awc-issue");
                if (target) {
                  emit(GRAMMAR_EVENTS.hoverEnd, {});
                }
                return false;
              },
            },
            handleClickOn(view, pos, _node, _nodePos, event) {
              const pluginState = grammarPluginKey.getState(view.state);
              const target = event.target as HTMLElement | null;
              if (target?.closest?.(".awc-hint-card")) {
                return false; // let the floating card handle its own clicks
              }
              const hit = pluginState?.issues.find((item) => pos >= item.from && pos <= item.to);
              if (hit) {
                emit(GRAMMAR_EVENTS.teach, { issueId: hit.issue.id });
                return true;
              }
              return false;
            },
          },
        }),
      ];
    },
  });
}

export function getGrammarIssues(view: EditorView): GrammarIssueState[] {
  return grammarPluginKey.getState(view.state)?.issues ?? [];
}
