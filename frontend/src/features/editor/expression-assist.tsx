"use client";

/**
 * Expression assistance (PRD FR-02.8/FR-03/FR-06, API Spec §8).
 *
 * Inline-first: selecting text offers "Improve expression"; selecting Chinese
 * text offers "Translate to English". Candidates appear in a floating card
 * near the selection. Acceptance is server-authoritative: the replacement
 * document is submitted to the accept endpoint (atomic), then applied — no
 * local edit races with autosave. Previously-learned candidates are labeled.
 * After acceptance the user can save the expression to the knowledge base.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { useQueryClient } from "@tanstack/react-query";

import type { AutosaveApi } from "@/features/editor/use-autosave";
import { ApiClientError } from "@/lib/api-client";
import { BLOCK_SEPARATOR, countWords, sentenceAround } from "@/lib/document-text";
import { codepointToUtf16, pmRangeToCodepoints } from "@/lib/text-positions";
import {
  acceptExpressionSuggestion,
  createExpression,
  polishExpression,
  translateChinese,
} from "@/services/expressions";
import type { SessionData, SuggestionData, SuggestionItemData, TipTapDocument } from "@/types/api";

const CJK_RE = /[\u4e00-\u9fff]/;

interface AssistState {
  mode: "polish" | "translation";
  top: number;
  left: number;
  from: number;
  to: number;
  selectedText: string;
  loading: boolean;
  error: string | null;
  suggestion: SuggestionData | null;
  acceptedItem: SuggestionItemData | null;
  savedToKb: boolean;
}

export function ExpressionAssist({
  essayId,
  editor,
  session,
  autosave,
  applyContent,
}: {
  essayId: string;
  editor: Editor | null;
  session: SessionData | null;
  autosave: AutosaveApi;
  applyContent: (content: TipTapDocument) => void;
}) {
  const queryClient = useQueryClient();
  const [assist, setAssist] = useState<AssistState | null>(null);
  const assistRef = useRef<AssistState | null>(null);
  const autosaveRef = useRef(autosave);
  const sessionRef = useRef(session);
  const applyContentRef = useRef(applyContent);
  useEffect(() => {
    assistRef.current = assist;
    autosaveRef.current = autosave;
    sessionRef.current = session;
    applyContentRef.current = applyContent;
  });

  const enabled = Boolean(
    session &&
      (session.enabled_features.expression_recommendations ||
        session.enabled_features.chinese_to_english),
  );
  const enabledRef = useRef(enabled);
  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  // Offer assistance when the user selects text (or Chinese text at caret).
  useEffect(() => {
    if (!editor) {
      return;
    }
    const onSelection = () => {
      if (!enabledRef.current) {
        return;
      }
      const { from, to } = editor.state.selection;
      if (from === to) {
        return;
      }
      const selectedText = editor.state.doc.textBetween(from, to, " ");
      if (selectedText.trim() === "") {
        return;
      }
      const coords = editor.view.coordsAtPos(to);
      const isChinese = CJK_RE.test(selectedText);
      const currentSession = sessionRef.current;
      if (isChinese && !currentSession?.enabled_features.chinese_to_english) {
        return;
      }
      if (!isChinese && !currentSession?.enabled_features.expression_recommendations) {
        return;
      }
      setAssist((previous) =>
        previous && !previous.loading && previous.suggestion
          ? previous // keep an open suggestion card until dismissed
          : {
              mode: isChinese ? "translation" : "polish",
              top: coords.bottom + 6,
              left: Math.max(8, coords.left),
              from,
              to,
              selectedText,
              loading: false,
              error: null,
              suggestion: null,
              acceptedItem: null,
              savedToKb: false,
            },
      );
    };
    editor.on("selectionUpdate", onSelection);
    return () => {
      editor.off("selectionUpdate", onSelection);
    };
  }, [editor]);

  const requestSuggestions = useCallback(async () => {
    const current = assistRef.current;
    const currentEditor = editor;
    const currentSession = sessionRef.current;
    const save = autosaveRef.current;
    if (!current || !currentEditor || !currentSession || save.status !== "saved") {
      return;
    }
    setAssist({ ...current, loading: true, error: null });
    const plainText = currentEditor.getText({ blockSeparator: BLOCK_SEPARATOR });
    const cp = pmRangeToCodepoints(currentEditor.state.doc, current.from, current.from).start;
    const [sentence] = sentenceAround(plainText, codepointToUtf16(plainText, cp));
    try {
      const response =
        current.mode === "polish"
          ? await polishExpression(essayId, {
              session_id: currentSession.id,
              server_revision: save.serverRevision,
              client_revision: save.clientRevision,
              selected_text: current.selectedText,
              sentence,
              paragraph_context: sentence,
              max_suggestions: 3,
            })
          : await translateChinese(essayId, {
              session_id: currentSession.id,
              server_revision: save.serverRevision,
              client_revision: save.clientRevision,
              chinese_text: current.selectedText,
              sentence_context: sentence,
              paragraph_context: sentence,
            });
      setAssist((previous) =>
        previous ? { ...previous, loading: false, suggestion: response.data } : previous,
      );
    } catch (error) {
      setAssist((previous) =>
        previous
          ? {
              ...previous,
              loading: false,
              error:
                error instanceof ApiClientError ? error.message : "表达辅助暂时不可用。",
            }
          : previous,
      );
    }
  }, [essayId, editor]);

  const acceptItem = useCallback(
    async (item: SuggestionItemData) => {
      const current = assistRef.current;
      const currentEditor = editor;
      const save = autosaveRef.current;
      if (!current || !currentEditor || save.status !== "saved") {
        return;
      }
      // Build the replacement document without touching the live editor:
      // acceptance is server-authoritative and avoids autosave races.
      const tr = currentEditor.state.tr.insertText(item.english_text, current.from, current.to);
      const newDoc = tr.doc;
      const contentJson = newDoc.toJSON() as TipTapDocument;
      const plainText = newDoc.textBetween(0, newDoc.content.size, BLOCK_SEPARATOR);
      const range = pmRangeToCodepoints(currentEditor.state.doc, current.from, current.to);
      try {
        const response = await acceptExpressionSuggestion(essayId, current.suggestion!.id, {
          item_id: item.id,
          base_revision: save.serverRevision,
          client_revision: save.clientRevision,
          content_json: contentJson,
          plain_text: plainText,
          word_count: countWords(plainText),
          modified_range: { ...range, offset_unit: "unicode_codepoint" },
        });
        applyContentRef.current(response.data.content_json);
        autosaveRef.current.setServerRevision(response.data.server_revision);
        void queryClient.invalidateQueries({ queryKey: ["essay", essayId] });
        setAssist((previous) =>
          previous ? { ...previous, acceptedItem: item, suggestion: null } : previous,
        );
      } catch (error) {
        setAssist((previous) =>
          previous
            ? {
                ...previous,
                error:
                  error instanceof ApiClientError
                    ? error.message
                    : "无法应用该表达。",
              }
            : previous,
        );
      }
    },
    [editor, essayId, queryClient],
  );

  const saveToKnowledgeBase = useCallback(async () => {
    const current = assistRef.current;
    if (!current?.acceptedItem) {
      return;
    }
    const item = current.acceptedItem;
    try {
      await createExpression({
        english_text: item.english_text,
        chinese_meaning: item.chinese_meaning,
        usage_context: item.usage_note,
        register: item.register,
        source_type: current.mode === "translation" ? "translation" : "suggestion",
        essay_id: essayId,
        source_context: current.selectedText,
      });
      setAssist((previous) => (previous ? { ...previous, savedToKb: true } : previous));
      void queryClient.invalidateQueries({ queryKey: ["expressions"] });
    } catch (error) {
      setAssist((previous) =>
        previous
          ? {
              ...previous,
              error:
                error instanceof ApiClientError
                  ? error.message
                  : "无法保存到知识库。",
            }
          : previous,
      );
    }
  }, [essayId, queryClient]);

  if (!assist || !enabled) {
    return null;
  }

  return (
    <div
      data-testid="expression-assist"
      className="fixed z-40 w-96 max-w-[calc(100vw-2rem)] rounded-lg border border-zinc-200/70 bg-white/95 p-3 shadow-lg backdrop-blur-sm dark:border-zinc-700/70 dark:bg-zinc-900/95"
      style={{
        top: Math.min(assist.top, window.innerHeight - 260),
        left: Math.max(8, Math.min(assist.left, window.innerWidth - 400)),
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
          {assist.mode === "polish" ? "表达润色" : "中译英"}
        </p>
        <button
          type="button"
          aria-label="关闭表达辅助"
          data-testid="close-expression-assist"
          onClick={() => setAssist(null)}
          className="rounded px-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800"
        >
          ×
        </button>
      </div>

      {!assist.suggestion && !assist.acceptedItem && (
        <button
          type="button"
          data-testid="request-suggestions"
          disabled={assist.loading}
          onClick={() => void requestSuggestions()}
          className="mt-2 w-full rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {assist.loading
            ? "思考中…"
            : assist.mode === "polish"
              ? `为“${assist.selectedText.slice(0, 40)}”推荐更地道的写法`
              : `翻译“${assist.selectedText.slice(0, 40)}”`}
        </button>
      )}

      {assist.error && (
        <p role="alert" className="mt-2 text-xs text-red-600 dark:text-red-400">
          {assist.error}
        </p>
      )}

      {assist.suggestion && (
        <ul className="mt-2 space-y-2" data-testid="expression-candidates">
          {assist.suggestion.items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                data-testid={`expression-item-${item.id}`}
                onClick={() => void acceptItem(item)}
                className="w-full rounded-md border border-zinc-200 p-2 text-left hover:border-zinc-400 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:border-zinc-500 dark:hover:bg-zinc-800"
              >
                <span className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {item.english_text}
                  </span>
                  {item.previously_learned && (
                    <span
                      data-testid="previously-learned-badge"
                      className="rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300"
                    >
                      曾学过
                    </span>
                  )}
                </span>
                {item.chinese_meaning && (
                  <span className="mt-0.5 block text-xs text-zinc-500 dark:text-zinc-400">
                    {item.chinese_meaning}
                  </span>
                )}
                {item.usage_note && (
                  <span className="mt-0.5 block text-xs text-zinc-400 dark:text-zinc-500">
                    {item.usage_note}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {assist.acceptedItem && (
        <div className="mt-2" data-testid="expression-accepted">
          <p className="text-xs text-emerald-700 dark:text-emerald-400">
            已应用：<strong>{assist.acceptedItem.english_text}</strong>
          </p>
          {assist.savedToKb ? (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              已保存到知识库。
            </p>
          ) : (
            <button
              type="button"
              data-testid="save-to-kb"
              onClick={() => void saveToKnowledgeBase()}
              className="mt-2 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              加入知识库
            </button>
          )}
        </div>
      )}
    </div>
  );
}
