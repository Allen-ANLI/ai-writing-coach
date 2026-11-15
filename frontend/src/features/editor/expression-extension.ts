/**
 * 表达润色下划线（ADR-026）：不地道片段以琥珀色虚线标注，
 * 悬浮/点击弹出选项卡。装饰不进入持久化正文与字数；
 * 范围随事务映射，不可靠映射丢弃。
 */

import { Extension } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";

import type { PolishSentenceFragment } from "@/types/api";

export interface PolishFragmentState {
  fragment: PolishSentenceFragment;
  from: number;
  to: number;
}

interface PolishPluginState {
  fragments: PolishFragmentState[];
}

export const POLISH_EVENTS = {
  hover: "awc-polish:hover",
  hoverEnd: "awc-polish:hover-end",
} as const;

function emit(name: string, detail: Record<string, unknown>) {
  document.dispatchEvent(new CustomEvent(name, { detail }));
}

export const polishPluginKey = new PluginKey<PolishPluginState>("awcPolish");

export type PolishMeta =
  | { type: "set"; fragments: PolishFragmentState[] }
  | { type: "remove"; suggestionId: string };

function buildDecorations(doc: ProseMirrorNode, fragments: PolishFragmentState[]): DecorationSet {
  const decorations: Decoration[] = [];
  const docSize = doc.content.size;
  for (const item of fragments) {
    if (item.from < 0 || item.to > docSize || item.from >= item.to) {
      continue;
    }
    decorations.push(
      Decoration.inline(item.from, item.to, {
        class: "awc-expression",
        "data-suggestion-id": item.fragment.suggestion_id,
      }),
    );
  }
  return DecorationSet.create(doc, decorations);
}

export function createExpressionExtension() {
  return Extension.create({
    name: "awcExpression",

    addProseMirrorPlugins() {
      return [
        new Plugin<PolishPluginState>({
          key: polishPluginKey,
          state: {
            init: () => ({ fragments: [] }),
            apply(tr, previous) {
              let fragments = previous.fragments;
              if (tr.docChanged) {
                fragments = fragments
                  .map((item) => ({
                    ...item,
                    from: tr.mapping.map(item.from),
                    to: tr.mapping.map(item.to, 1),
                  }))
                  .filter((item) => item.from < item.to);
              }
              const meta = tr.getMeta(polishPluginKey) as PolishMeta | undefined;
              if (meta?.type === "set") {
                fragments = meta.fragments;
              } else if (meta?.type === "remove") {
                fragments = fragments.filter(
                  (item) => item.fragment.suggestion_id !== meta.suggestionId,
                );
              }
              return { fragments };
            },
          },
          props: {
            decorations(state) {
              const pluginState = polishPluginKey.getState(state);
              if (!pluginState || pluginState.fragments.length === 0) {
                return DecorationSet.empty;
              }
              return buildDecorations(state.doc, pluginState.fragments);
            },
            handleDOMEvents: {
              mouseover(view, event) {
                const target = (event.target as HTMLElement | null)?.closest?.(".awc-expression");
                const suggestionId = target?.getAttribute("data-suggestion-id");
                if (suggestionId) {
                  const rect = (target as HTMLElement).getBoundingClientRect();
                  emit(POLISH_EVENTS.hover, {
                    suggestionId,
                    top: rect.bottom,
                    left: rect.left,
                  });
                }
                return false;
              },
              mouseout(view, event) {
                const target = (event.target as HTMLElement | null)?.closest?.(".awc-expression");
                if (target) {
                  emit(POLISH_EVENTS.hoverEnd, {});
                }
                return false;
              },
            },
            handleClickOn(view, pos, _node, _nodePos, event) {
              const pluginState = polishPluginKey.getState(view.state);
              const target = event.target as HTMLElement | null;
              if (target?.closest?.(".awc-polish-card")) {
                return false;
              }
              const hit = pluginState?.fragments.find(
                (item) => pos >= item.from && pos <= item.to,
              );
              if (hit) {
                const rect = (event.target as HTMLElement).getBoundingClientRect();
                emit(POLISH_EVENTS.hover, {
                  suggestionId: hit.fragment.suggestion_id,
                  top: rect.bottom,
                  left: rect.left,
                  pinned: true,
                });
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

export function getPolishFragments(view: EditorView): PolishFragmentState[] {
  return polishPluginKey.getState(view.state)?.fragments ?? [];
}
