/**
 * 灰色中文写作指引（ADR-024，取代旧版编辑器上方横幅）：
 * 基于已确认大纲，在光标所在的空段落/未完成段落处显示"下一句该写什么"。
 * - Decoration.widget 实现：不进入持久化正文，不计入字数。
 * - 开始输入、移动光标或点击提示即消失；按段落序号与已写句数推进。
 * - 提示是写作指引，不会把中文插入英文正文（AI 不代写不变量）。
 */

import { Extension } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { Plugin, PluginKey, type EditorState } from "@tiptap/pm/state";
import { Decoration, DecorationSet, type EditorView } from "@tiptap/pm/view";

import { splitSentences } from "@/lib/document-text";

export interface GhostParagraph {
  ideas: string[];
}

interface GhostPluginState {
  paragraphs: GhostParagraph[];
  dismissed: Set<string>;
}

export const ghostHintPluginKey = new PluginKey<GhostPluginState>("awcGhostHint");

export type GhostHintMeta =
  | { type: "set-plan"; paragraphs: GhostParagraph[] }
  | { type: "dismiss"; key: string };

function paragraphOrdinal(doc: ProseMirrorNode, topLevelIndex: number): number {
  let ordinal = 0;
  for (let i = 0; i < topLevelIndex; i += 1) {
    if (doc.child(i).type.name === "paragraph") {
      ordinal += 1;
    }
  }
  return ordinal;
}

function currentHint(
  pluginState: GhostPluginState,
  state: EditorState,
): { pos: number; key: string; text: string } | null {
  const { selection, doc } = state;
  if (!selection.empty || pluginState.paragraphs.length === 0) {
    return null;
  }
  const $from = selection.$from;
  if ($from.depth < 1 || $from.parent.type.name !== "paragraph") {
    return null;
  }
  const topLevelIndex = $from.index(0);
  if (doc.child(topLevelIndex).type.name !== "paragraph") {
    return null;
  }
  const ordinal = paragraphOrdinal(doc, topLevelIndex);
  const paragraph = pluginState.paragraphs[ordinal];
  if (!paragraph || paragraph.ideas.length === 0) {
    return null;
  }
  const text = $from.parent.textContent;
  const written = splitSentences(text).filter((s) => s.text.trim() !== "").length;
  const caretAtEnd = $from.parentOffset === $from.parent.content.size;
  let ideaIndex: number;
  if (text.trim() === "") {
    ideaIndex = 0;
  } else if (caretAtEnd && written < paragraph.ideas.length) {
    ideaIndex = written;
  } else {
    return null;
  }
  const key = `${ordinal}:${ideaIndex}`;
  if (pluginState.dismissed.has(key)) {
    return null;
  }
  return { pos: selection.from, key, text: paragraph.ideas[ideaIndex] };
}

export function createGhostHintExtension() {
  return Extension.create({
    name: "awcGhostHint",

    addProseMirrorPlugins() {
      return [
        new Plugin<GhostPluginState>({
          key: ghostHintPluginKey,
          state: {
            init: () => ({ paragraphs: [], dismissed: new Set<string>() }),
            apply(tr, previous) {
              const meta = tr.getMeta(ghostHintPluginKey) as GhostHintMeta | undefined;
              if (meta?.type === "set-plan") {
                return { paragraphs: meta.paragraphs, dismissed: new Set<string>() };
              }
              if (meta?.type === "dismiss") {
                const dismissed = new Set(previous.dismissed);
                dismissed.add(meta.key);
                return { ...previous, dismissed };
              }
              return previous;
            },
          },
          props: {
            decorations(state) {
              const pluginState = ghostHintPluginKey.getState(state);
              if (!pluginState) {
                return DecorationSet.empty;
              }
              const hint = currentHint(pluginState, state);
              if (!hint) {
                return DecorationSet.empty;
              }
              const widget = Decoration.widget(
                hint.pos,
                (view) => {
                  const span = document.createElement("span");
                  span.className = "awc-ghost-hint";
                  span.contentEditable = "false";
                  span.setAttribute("data-testid", "ghost-hint");
                  span.setAttribute("data-ghost-key", hint.key);
                  span.textContent = `💡 ${hint.text}（点击关闭）`;
                  span.addEventListener("mousedown", (event) => {
                    event.preventDefault();
                    view.dispatch(
                      view.state.tr.setMeta(ghostHintPluginKey, {
                        type: "dismiss",
                        key: hint.key,
                      } satisfies GhostHintMeta),
                    );
                  });
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

export function setGhostPlan(view: EditorView, paragraphs: GhostParagraph[]) {
  view.dispatch(
    view.state.tr.setMeta(ghostHintPluginKey, {
      type: "set-plan",
      paragraphs,
    } satisfies GhostHintMeta),
  );
}
