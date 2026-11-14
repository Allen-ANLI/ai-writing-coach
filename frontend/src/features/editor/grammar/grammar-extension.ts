/**
 * Grammar feedback extension (inline-first, PRD FR-02.3/FR-02.4).
 *
 * - Inline decorations underline issue ranges (color by category).
 * - A widget directly after the error shows the short explanation and a
 *   BLURRED correction until the user explicitly reveals it.
 * - Decorations/widgets are never part of the persisted document or word count.
 * - Issue ranges map through document transactions; unreliable mappings are
 *   dropped (AGENTS: never apply old offsets to new text blindly).
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

/** DOM events bridging ProseMirror widgets to the React layer (subscribed in
 * effects, so no render-phase closures over mutable values). */
export const GRAMMAR_EVENTS = {
  reveal: "awc-grammar:reveal",
  ignore: "awc-grammar:ignore",
  teach: "awc-grammar:teach",
} as const;

function emit(name: string, issueId: string) {
  document.dispatchEvent(new CustomEvent(name, { detail: { issueId } }));
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
    decorations.push(
      Decoration.widget(item.to, () => buildHintWidget(item), {
        side: 1,
        key: `hint-${item.issue.id}-${item.revealed ? "r" : "m"}`,
        ignoreSelection: true,
      }),
    );
  }
  return DecorationSet.create(doc, decorations);
}

function buildHintWidget(item: GrammarIssueState): HTMLElement {
  const wrap = document.createElement("span");
  wrap.className = "awc-hint";
  wrap.setAttribute("data-issue-id", item.issue.id);
  wrap.contentEditable = "false";

  const text = document.createElement("span");
  text.className = "awc-hint__text";
  text.textContent = item.issue.short_explanation ?? "";
  wrap.appendChild(text);

  const answer = document.createElement("span");
  const recommended = item.revealed?.find((s) => s.is_recommended) ?? item.revealed?.[0];
  if (recommended) {
    answer.className = "awc-hint__answer awc-hint__answer--revealed";
    answer.textContent = recommended.suggested_text;
  } else {
    answer.className = "awc-hint__answer";
    answer.textContent = "••••";
    answer.title = "Press Reveal (Alt+R) to see the suggested correction";
  }
  wrap.appendChild(answer);

  const actions = document.createElement("span");
  actions.className = "awc-hint__actions";

  if (!item.revealed) {
    const reveal = document.createElement("button");
    reveal.type = "button";
    reveal.textContent = "Reveal";
    reveal.setAttribute("data-testid", `reveal-${item.issue.id}`);
    reveal.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      emit(GRAMMAR_EVENTS.reveal, item.issue.id);
    });
    actions.appendChild(reveal);
  }

  const teach = document.createElement("button");
  teach.type = "button";
  teach.textContent = "Teach me";
  teach.setAttribute("data-testid", `teach-${item.issue.id}`);
  teach.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    emit(GRAMMAR_EVENTS.teach, item.issue.id);
  });
  actions.appendChild(teach);

  const ignore = document.createElement("button");
  ignore.type = "button";
  ignore.textContent = "Ignore";
  ignore.setAttribute("data-testid", `ignore-${item.issue.id}`);
  ignore.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    emit(GRAMMAR_EVENTS.ignore, item.issue.id);
  });
  actions.appendChild(ignore);

  wrap.appendChild(actions);
  return wrap;
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
            handleClickOn(view, pos, _node, _nodePos, event) {
              const pluginState = grammarPluginKey.getState(view.state);
              const target = event.target as HTMLElement | null;
              const hintIssueId = target?.closest?.(".awc-hint")?.getAttribute("data-issue-id");
              if (hintIssueId) {
                emit(GRAMMAR_EVENTS.teach, hintIssueId);
                return true;
              }
              const hit = pluginState?.issues.find((item) => pos >= item.from && pos <= item.to);
              if (hit) {
                emit(GRAMMAR_EVENTS.teach, hit.issue.id);
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
