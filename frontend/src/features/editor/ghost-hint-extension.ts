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

/** ADR-037: the widget's 表达·句式 button asks the React layer to open the
 * pre-extracted annotation card for the current hint sentence. */
export const GHOST_EVENTS = {
  insight: "awc-ghost:insight",
} as const;

export type GhostHintMeta =
  | { type: "config"; ideas: string[]; enabled: boolean }
  | { type: "advance" }
  | { type: "set-index"; index: number };

/** ADR-026: the hint sits at the END of the written text (last non-empty
 * block), not at the caret — it guides what to write next. */
function endOfTextPos(state: EditorState): number | null {
  const { doc } = state;
  const blocks: { offset: number; nodeSize: number }[] = [];
  doc.forEach((node, offset) => {
    if (node.textContent.trim() !== "") {
      blocks.push({ offset, nodeSize: node.nodeSize });
    }
  });
  const last = blocks[blocks.length - 1];
  if (last) {
    return last.offset + last.nodeSize - 1; // inside the block, after its last character
  }
  if (doc.firstChild) {
    return 1; // empty document: start of the first paragraph
  }
  return null;
}

function currentIdea(state: EditorState): { pos: number; text: string; index: number } | null {
  const pluginState = ghostHintPluginKey.getState(state);
  if (!pluginState || !pluginState.enabled) {
    return null;
  }
  const idea = pluginState.ideas[pluginState.index];
  if (!idea) {
    return null; // outline guidance exhausted
  }
  const pos = endOfTextPos(state);
  if (pos === null) {
    return null;
  }
  return { pos, text: idea, index: pluginState.index };
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
                  const text = document.createElement("span");
                  text.textContent = `💡 ${hint.text}`;
                  span.appendChild(text);
                  // ADR-037: annotations are pre-extracted at generation time;
                  // the button only opens the card (no LLM call, no quota).
                  const button = document.createElement("button");
                  button.type = "button";
                  button.className = "awc-ghost-insight-btn";
                  button.setAttribute("data-testid", "ghost-insight-open");
                  button.textContent = "表达·句式";
                  button.addEventListener("mousedown", (event) => {
                    event.preventDefault(); // keep caret/focus in the editor
                  });
                  button.addEventListener("click", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const rect = button.getBoundingClientRect();
                    document.dispatchEvent(
                      new CustomEvent(GHOST_EVENTS.insight, {
                        detail: { index: hint.index, top: rect.bottom, left: rect.left },
                      }),
                    );
                  });
                  span.appendChild(button);
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

export function setGhostIndex(view: EditorView, index: number) {
  view.dispatch(
    view.state.tr.setMeta(ghostHintPluginKey, { type: "set-index", index } satisfies GhostHintMeta),
  );
}
