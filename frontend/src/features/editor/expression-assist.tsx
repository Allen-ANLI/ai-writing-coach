"use client";

/**
 * 中译英表达辅助（ADR-027，取代选区+按钮式辅助）：
 * 光标处输入中文即自动结合整句推荐可直接替换的英文表达，无需选区、
 * 悬浮或点击请求；选项卡与表达润色一致（点选、Tab/点击替换、查看更多
 * 翻页、加入知识库）。接受走服务端原子替换，最小差异应用保留其余高亮。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { useQueryClient } from "@tanstack/react-query";

import {
  ChineseAssistCard,
  type AssistCardState,
  type AssistPage,
} from "@/features/editor/chinese-assist-card";
import type { AutosaveApi } from "@/features/editor/use-autosave";
import { ApiClientError } from "@/lib/api-client";
import { findChineseRunAt } from "@/lib/chinese-run";
import { BLOCK_SEPARATOR, countWords, sentenceAround } from "@/lib/document-text";
import { codepointToUtf16, pmRangeToCodepoints } from "@/lib/text-positions";
import {
  acceptExpressionSuggestion,
  createExpression,
  translateChinese,
} from "@/services/expressions";
import type { SessionData, TipTapDocument } from "@/types/api";

const REQUEST_DEBOUNCE_MS = 250;

interface DetectedRun {
  from: number;
  to: number;
  text: string;
  key: string;
}

/** Chinese run touching the caret, in ProseMirror positions. */
function detectRun(editor: Editor): DetectedRun | null {
  const selection = editor.state.selection;
  if (!selection.empty) {
    return null;
  }
  const $from = selection.$from;
  if (!$from.parent.isTextblock) {
    return null;
  }
  const run = findChineseRunAt($from.parent.textContent, $from.parentOffset);
  if (!run || run.text.trim() === "") {
    return null;
  }
  const base = $from.start();
  const from = base + run.start;
  const to = base + run.end;
  return { from, to, text: run.text, key: `${from}:${to}:${run.text}` };
}

function positionFor(editor: Editor, to: number): { top: number; left: number } {
  const coords = editor.view.coordsAtPos(to);
  return { top: coords.bottom + 6, left: Math.max(8, coords.left) };
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
  const enabled = Boolean(session?.enabled_features.chinese_to_english);
  const [card, setCard] = useState<AssistCardState | null>(null);

  const cardRef = useRef<AssistCardState | null>(card);
  const editorRef = useRef<Editor | null>(editor);
  const sessionRef = useRef(session);
  const autosaveRef = useRef(autosave);
  const applyContentRef = useRef(applyContent);
  const enabledRef = useRef(enabled);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastRequestedKeyRef = useRef<string | null>(null);
  const dismissedKeyRef = useRef<string | null>(null);
  const requestingRef = useRef(false);
  // Re-entering an unchanged run re-shows cached options instantly (no spend).
  const cacheRef = useRef<Map<string, AssistPage[]>>(new Map());

  useEffect(() => {
    cardRef.current = card;
    editorRef.current = editor;
    sessionRef.current = session;
    autosaveRef.current = autosave;
    applyContentRef.current = applyContent;
    enabledRef.current = enabled;
  });

  const setCardState = useCallback((next: AssistCardState | null) => {
    cardRef.current = next;
    setCard(next);
  }, []);

  const patchCard = useCallback(
    (runKey: string, patch: Partial<AssistCardState>) => {
      const current = cardRef.current;
      if (!current || current.runKey !== runKey) {
        return;
      }
      setCardState({ ...current, ...patch });
    },
    [setCardState],
  );

  const sentenceContextFor = useCallback((current: Editor, pmPos: number): string => {
    const plainText = current.getText({ blockSeparator: BLOCK_SEPARATOR });
    const cp = pmRangeToCodepoints(current.state.doc, pmPos, pmPos).start;
    const [sentence] = sentenceAround(plainText, codepointToUtf16(plainText, cp));
    return sentence.trim();
  }, []);

  // --- Automatic request -----------------------------------------------------

  const requestRun = useCallback(
    async (run: DetectedRun) => {
      const current = editorRef.current;
      const currentSession = sessionRef.current;
      const save = autosaveRef.current;
      if (!current || !currentSession || !enabledRef.current || save.status !== "saved") {
        return;
      }
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      lastRequestedKeyRef.current = run.key;
      requestingRef.current = true;
      setCardState({
        runKey: run.key,
        from: run.from,
        to: run.to,
        chineseText: run.text,
        ...positionFor(current, run.to),
        pages: [],
        pageIndex: 0,
        selectedItemId: null,
        loading: true,
        loadingMore: false,
        error: null,
        moreError: null,
        savedToKb: false,
      });
      const sentence = sentenceContextFor(current, run.from) || run.text;
      try {
        const response = await translateChinese(
          essayId,
          {
            session_id: currentSession.id,
            server_revision: save.serverRevision,
            client_revision: save.clientRevision,
            chinese_text: run.text,
            sentence_context: sentence,
            paragraph_context: sentence,
          },
          controller.signal,
        );
        if (controller.signal.aborted) {
          return;
        }
        const latest = editorRef.current;
        const active = cardRef.current;
        if (!latest || !active || active.runKey !== run.key) {
          return; // a newer run took over while the request was in flight
        }
        if (latest.state.doc.textBetween(run.from, run.to) !== run.text) {
          return; // run edited meanwhile; the newer schedule re-requests
        }
        const items = response.data.items;
        const pages: AssistPage[] = [{ suggestionId: response.data.id, items }];
        if (cacheRef.current.size > 20) {
          cacheRef.current.clear();
        }
        cacheRef.current.set(run.key, pages);
        patchCard(run.key, {
          pages,
          pageIndex: 0,
          selectedItemId: items[0]?.id ?? null,
          loading: false,
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        patchCard(run.key, {
          loading: false,
          error:
            error instanceof ApiClientError ? error.message : "表达推荐暂时不可用，请重试。",
        });
      } finally {
        requestingRef.current = false;
      }
    },
    [essayId, patchCard, sentenceContextFor, setCardState],
  );

  const scheduleAssist = useCallback(
    (delay = REQUEST_DEBOUNCE_MS) => {
      const current = editorRef.current;
      if (!current || !enabledRef.current) {
        return;
      }
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        const latest = editorRef.current;
        if (!latest || !enabledRef.current) {
          return;
        }
        const run = detectRun(latest);
        if (!run) {
          lastRequestedKeyRef.current = null;
          if (cardRef.current) {
            setCardState(null);
          }
          return;
        }
        if (dismissedKeyRef.current === run.key) {
          return; // user pressed Esc on this exact run
        }
        const active = cardRef.current;
        if (active && active.runKey === run.key) {
          const pos = positionFor(latest, run.to);
          if (active.top !== pos.top || active.left !== pos.left) {
            patchCard(run.key, pos);
          }
          return;
        }
        if (lastRequestedKeyRef.current === run.key && requestingRef.current) {
          return;
        }
        if (autosaveRef.current.status !== "saved") {
          return; // the saved-effect re-triggers once the revision is ready
        }
        const cached = cacheRef.current.get(run.key);
        if (cached && cached.length > 0) {
          lastRequestedKeyRef.current = run.key;
          setCardState({
            runKey: run.key,
            from: run.from,
            to: run.to,
            chineseText: run.text,
            ...positionFor(latest, run.to),
            pages: cached,
            pageIndex: 0,
            selectedItemId: cached[0].items[0]?.id ?? null,
            loading: false,
            loadingMore: false,
            error: null,
            moreError: null,
            savedToKb: false,
          });
          return;
        }
        void requestRun(run);
      }, delay);
    },
    [patchCard, requestRun, setCardState],
  );

  // Typing / IME commit / caret moves / completed saves all re-evaluate.
  useEffect(() => {
    if (!editor) {
      return;
    }
    const onUpdate = ({ transaction }: { transaction: import("@tiptap/pm/state").Transaction }) => {
      if (!transaction.docChanged || !enabledRef.current) {
        return;
      }
      const current = editorRef.current;
      if (!current || current.view.composing) {
        return; // IME: wait for compositionend
      }
      scheduleAssist();
    };
    const onSelection = () => {
      const current = editorRef.current;
      if (!current || !enabledRef.current) {
        return;
      }
      const active = cardRef.current;
      const run = detectRun(current);
      if (active && (!run || run.from !== active.from)) {
        // Caret left the run (or jumped to another one): close; re-entry
        // re-shows from cache without a new request.
        setCardState(null);
        lastRequestedKeyRef.current = null;
      }
      scheduleAssist(120);
    };
    const onCompositionEnd = () => scheduleAssist(80);
    editor.on("update", onUpdate);
    editor.on("selectionUpdate", onSelection);
    editor.view.dom.addEventListener("compositionend", onCompositionEnd);
    return () => {
      editor.off("update", onUpdate);
      editor.off("selectionUpdate", onSelection);
      editor.view.dom.removeEventListener("compositionend", onCompositionEnd);
    };
  }, [editor, scheduleAssist, setCardState]);

  useEffect(() => {
    if (!enabled || autosave.status !== "saved") {
      return;
    }
    const timer = setTimeout(() => scheduleAssist(100), 100);
    return () => clearTimeout(timer);
  }, [enabled, autosave.status, autosave.serverRevision, scheduleAssist]);

  useEffect(() => () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    abortRef.current?.abort();
  }, []);

  // --- Selection / accept ------------------------------------------------------

  const selectItem = useCallback(
    (itemId: string) => {
      const current = cardRef.current;
      if (current) {
        patchCard(current.runKey, { selectedItemId: itemId, savedToKb: false });
      }
    },
    [patchCard],
  );

  const acceptSelected = useCallback(() => {
    const current = editorRef.current;
    const state = cardRef.current;
    const save = autosaveRef.current;
    if (!current || !state || !state.selectedItemId || save.status !== "saved") {
      return;
    }
    const page = state.pages[state.pageIndex];
    const item = page?.items.find((option) => option.id === state.selectedItemId);
    if (!page || !item) {
      return;
    }
    const run = detectRun(current);
    if (!run || run.text !== state.chineseText) {
      return; // options are stale for the edited run; refresh is pending
    }
    const tr = current.state.tr.insertText(item.english_text, run.from, run.to);
    const newDoc = tr.doc;
    const contentJson = newDoc.toJSON() as TipTapDocument;
    const plainText = newDoc.textBetween(0, newDoc.content.size, BLOCK_SEPARATOR);
    const range = pmRangeToCodepoints(current.state.doc, run.from, run.to);
    void acceptExpressionSuggestion(essayId, page.suggestionId, {
      item_id: item.id,
      base_revision: save.serverRevision,
      client_revision: save.clientRevision,
      content_json: contentJson,
      plain_text: plainText,
      word_count: countWords(plainText),
      modified_range: { ...range, offset_unit: "unicode_codepoint" },
    })
      .then((response) => {
        applyContentRef.current(response.data.content_json);
        autosaveRef.current.setServerRevision(response.data.server_revision);
        cacheRef.current.delete(state.runKey);
        lastRequestedKeyRef.current = null;
        dismissedKeyRef.current = null;
        setCardState(null);
        void queryClient.invalidateQueries({ queryKey: ["essay", essayId] });
      })
      .catch((error) => {
        patchCard(state.runKey, {
          error: error instanceof ApiClientError ? error.message : "无法应用该表达，请重试。",
        });
      });
  }, [essayId, patchCard, queryClient, setCardState]);

  // Tab replaces the selected option; Esc dismisses this run.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const state = cardRef.current;
      if (!state) {
        return;
      }
      if (event.key === "Tab" && state.selectedItemId && !state.loading) {
        event.preventDefault();
        event.stopPropagation();
        acceptSelected();
      } else if (event.key === "Escape") {
        dismissedKeyRef.current = state.runKey;
        setCardState(null);
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [acceptSelected, setCardState]);

  // --- Pagination ----------------------------------------------------------------

  const nextPage = useCallback(() => {
    const state = cardRef.current;
    const currentSession = sessionRef.current;
    const save = autosaveRef.current;
    const current = editorRef.current;
    if (!state || !currentSession || !current || save.status !== "saved") {
      return;
    }
    if (state.pageIndex < state.pages.length - 1) {
      const target = state.pages[state.pageIndex + 1];
      patchCard(state.runKey, {
        pageIndex: state.pageIndex + 1,
        selectedItemId: target.items[0]?.id ?? null,
        savedToKb: false,
        moreError: null,
      });
      return;
    }
    if (state.loadingMore) {
      return;
    }
    patchCard(state.runKey, { loadingMore: true, moreError: null });
    const exclude = state.pages.flatMap((p) => p.items.map((option) => option.english_text));
    const sentence = sentenceContextFor(current, state.from) || state.chineseText;
    void translateChinese(essayId, {
      session_id: currentSession.id,
      server_revision: save.serverRevision,
      client_revision: save.clientRevision,
      chinese_text: state.chineseText,
      sentence_context: sentence,
      paragraph_context: sentence,
      exclude,
    })
      .then((response) => {
        const fresh = response.data.items.filter(
          (option) => !exclude.includes(option.english_text),
        );
        const latest = cardRef.current;
        if (!latest || latest.runKey !== state.runKey) {
          return;
        }
        if (fresh.length > 0) {
          const pages = [...latest.pages, { suggestionId: response.data.id, items: fresh }];
          cacheRef.current.set(state.runKey, pages);
          patchCard(state.runKey, {
            pages,
            pageIndex: latest.pages.length,
            selectedItemId: fresh[0].id,
            loadingMore: false,
          });
        } else {
          patchCard(state.runKey, { loadingMore: false, moreError: "没有更多不同的表达了。" });
        }
      })
      .catch(() => {
        patchCard(state.runKey, { loadingMore: false, moreError: "获取更多表达失败。" });
      });
  }, [essayId, patchCard, sentenceContextFor]);

  const prevPage = useCallback(() => {
    const state = cardRef.current;
    if (state && state.pageIndex > 0) {
      const target = state.pages[state.pageIndex - 1];
      patchCard(state.runKey, {
        pageIndex: state.pageIndex - 1,
        selectedItemId: target.items[0]?.id ?? null,
        savedToKb: false,
        moreError: null,
      });
    }
  }, [patchCard]);

  // --- Knowledge base --------------------------------------------------------------

  const addSelectedToKb = useCallback(() => {
    const state = cardRef.current;
    if (!state || !state.selectedItemId) {
      return;
    }
    const item = state.pages
      .flatMap((p) => p.items)
      .find((option) => option.id === state.selectedItemId);
    if (!item) {
      return;
    }
    void createExpression({
      english_text: item.english_text,
      chinese_meaning: item.chinese_meaning,
      usage_context: item.usage_note,
      register: item.register,
      source_type: "translation",
      essay_id: essayId,
      source_context: state.chineseText,
    })
      .then(() => {
        patchCard(state.runKey, { savedToKb: true });
        void queryClient.invalidateQueries({ queryKey: ["expressions"] });
      })
      .catch(() => {
        patchCard(state.runKey, { moreError: "加入知识库失败（可能已存在）。" });
      });
  }, [essayId, patchCard, queryClient]);

  const closeCard = useCallback(() => {
    const state = cardRef.current;
    if (state) {
      dismissedKeyRef.current = state.runKey;
    }
    setCardState(null);
  }, [setCardState]);

  const retry = useCallback(() => {
    const current = editorRef.current;
    if (!current) {
      return;
    }
    const run = detectRun(current);
    if (run) {
      dismissedKeyRef.current = null;
      void requestRun(run);
    }
  }, [requestRun]);

  if (!card || !enabled) {
    return null;
  }

  return (
    <ChineseAssistCard
      state={card}
      onSelect={selectItem}
      onAccept={acceptSelected}
      onNextPage={nextPage}
      onPrevPage={prevPage}
      onAddToKb={addSelectedToKb}
      onClose={closeCard}
      onRetry={retry}
    />
  );
}