/**
 * 语法反馈扩展（ADR-024）：
 * - 内联装饰按类别给错误范围加下划线；反馈悬浮显示（React 层）。
 * - 悬浮事件经 DOM CustomEvent 桥接；点击错误只放置光标，不触发讲解
 *   （详细讲解在悬浮卡片内自动加载）。
 * - 装饰不进入持久化正文与字数；不可靠的位置映射直接丢弃。
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
  hover: "awc-grammar:hover",
  hoverEnd: "awc-grammar:hover-end",
} as const;

function emit(name: string, detail: Record<string, unknown>) {
  document.dispatchEvent(new CustomEvent(name, { detail }));
}

export const grammarPluginKey = new PluginKey<GrammarPluginState>("awcGrammar");

export type GrammarMeta =
  | { type: "set"; issues: GrammarIssueState[] }
  // ADR-025: replace only issues inside the checked sentence range; other
  // sentences' findings survive (multi-sentence underlines coexist).
  | { type: "merge"; start: number; end: number; issues: GrammarIssueState[] }
  // ADR-027: after an acceptance, mirror the server's range-scoped
  // reconciliation: drop the accepted issue and any issue intersecting the
  // replaced code-point range (staled server-side), shift the rest.
  | { type: "accept-shift"; startCp: number; endCp: number; delta: number; removedIssueId: string }
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
                  case "merge":
                    issues = [
                      ...issues.filter((item) => item.to <= meta.start || item.from >= meta.end),
                      ...meta.issues,
                    ];
                    break;
                  case "accept-shift":
                    issues = issues
                      .filter((item) => item.issue.id !== meta.removedIssueId)
                      .map((item) => {
                        if (item.issue.end_offset <= meta.startCp) {
                          return item;
                        }
                        if (item.issue.start_offset >= meta.endCp) {
                          return {
                            ...item,
                            issue: {
                              ...item.issue,
                              start_offset: item.issue.start_offset + meta.delta,
                              end_offset: item.issue.end_offset + meta.delta,
                            },
                          };
                        }
                        return null; // intersected the replacement: staled server-side
                      })
                      .filter((item): item is GrammarIssueState => item !== null);
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
          },
        }),
      ];
    },
  });
}

export function getGrammarIssues(view: EditorView): GrammarIssueState[] {
  return grammarPluginKey.getState(view.state)?.issues ?? [];
}
