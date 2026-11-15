/**
 * 灰色中文写作指引（ADR-025，取代 ADR-024 的段落级实现）：
 * - 已确认大纲展平为有序句子指引；当前指引在光标处持续显示，直到该句完成。
 * - 句点完成后由 React 层调用 planner/progress 判断是否达成指引：
 *   达成 → advance 到下一句；未达成 → 保持当前指引。贯穿整个大纲。
 * - 开关在左侧构思助手面板（preferences.ghost_hints_enabled），不再点击关闭。
 * - Decoration.widget：不持久化、不计字数、不代写。
 */

import { Extension } from "@tiptap/core";
import { Plugin, PluginKey, type EditorState } from "@tiptap/pm/state";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";

interface GhostPluginState {
  ideas: string[];
  enabled: boolean;
  index: number;
}

export const ghostHintPluginKey = new PluginKey<GhostPluginState>("awcGhostHint");

export type GhostHintMeta =
  | { type: "config"; ideas: string[]; enabled: boolean }
  | { type: "advance" }
  | { type: "set-index"; index: number };

function currentIdea(state: EditorState): { pos: number; text: string; index: number } | null {
  const pluginState = ghostHintPluginKey.getState(state);
  if (!pluginState || !pluginState.enabled) {
    return null;
  }
  const idea = pluginState.ideas[pluginState.index];
  if (!idea) {
    return null; // outline guidance exhausted
  }
  const { selection } = state;
  if (!selection.empty || selection.$from.parent.type.name !== "paragraph") {
    return null;
  }
  return { pos: selection.from, text: idea, index: pluginState.index };
}

export function createGhostHintExtension() {
  return Extension.create({
    name: "awcGhostHint",

    addProseMirrorPlugins() {
      return [
        new Plugin<GhostPluginState>({
          key: ghostHintPluginKey,
          state: {
            init: () => ({ ideas: [], enabled: true, index: 0 }),
            apply(tr, previous) {
              const meta = tr.getMeta(ghostHintPluginKey) as GhostHintMeta | undefined;
              if (meta?.type === "config") {
                // Keep progress when the idea list is unchanged; reset on a
                // new/revised outline so guidance matches the new plan.
                const samePlan =
                  meta.ideas.length === previous.ideas.length &&
                  meta.ideas.every((idea, i) => idea === previous.ideas[i]);
                return {
                  ideas: meta.ideas,
                  enabled: meta.enabled,
                  index: samePlan ? previous.index : 0,
                };
              }
              if (meta?.type === "advance") {
                return { ...previous, index: previous.index + 1 };
              }
              if (meta?.type === "set-index") {
                return { ...previous, index: meta.index };
              }
              return previous;
            },
          },
          props: {
            decorations(state) {
              const hint = currentIdea(state);
              if (!hint) {
                return DecorationSet.empty;
              }
              const widget = Decoration.widget(
                hint.pos,
                () => {
                  const span = document.createElement("span");
                  span.className = "awc-ghost-hint";
                  span.contentEditable = "false";
                  span.setAttribute("data-testid", "ghost-hint");
                  span.setAttribute("data-ghost-index", String(hint.index));
                  span.textContent = `💡 ${hint.text}`;
                  return span;
                },
                { side: 1, ignoreSelection: true },
              );
              return DecorationSet.create(state.doc, [widget]);
            },
          },
        }),
      ];
    },
  });
}

export function setGhostConfig(view: EditorView, ideas: string[], enabled: boolean) {
  view.dispatch(
    view.state.tr.setMeta(ghostHintPluginKey, {
      type: "config",
      ideas,
      enabled,
    } satisfies GhostHintMeta),
  );
}

export function advanceGhostHint(view: EditorView) {
  view.dispatch(
    view.state.tr.setMeta(ghostHintPluginKey, { type: "advance" } satisfies GhostHintMeta),
  );
}

export function getGhostIndex(view: EditorView): number {
  return ghostHintPluginKey.getState(view.state)?.index ?? 0;
}
