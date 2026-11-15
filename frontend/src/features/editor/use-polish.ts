"use client";

/**
 * 表达润色编排（ADR-026）：句点完成/修改已完成句触发片段级扫描；
 * 不地道片段自动下划线；选项卡支持选择、Tab/点击替换、翻页、加入知识库。
 * 自然的句子不产生任何提示。规则与调度镜像语法检查。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { useQueryClient } from "@tanstack/react-query";

import {
  POLISH_EVENTS,
  polishPluginKey,
  getPolishFragments,
  type PolishFragmentState,
  type PolishMeta,
} from "@/features/editor/expression-extension";
import type { AutosaveApi } from "@/features/editor/use-autosave";
import { ApiClientError } from "@/lib/api-client";
import { BLOCK_SEPARATOR, countWords, splitSentences } from "@/lib/document-text";
import { codepointRangeToPm, codepointToUtf16, pmRangeToCodepoints } from "@/lib/text-positions";
import {
  acceptExpressionSuggestion,
  createExpression,
  polishSentence,
} from "@/services/expressions";
import type {
  PolishSentenceFragment,
  PolishSentenceItem,
  SessionData,
  TipTapDocument,
} from "@/types/api";

export interface PolishCardState {
  suggestionId: string;
  top: number;
  left: number;
  fragment: PolishSentenceFragment;
  pages: PolishSentenceItem[][];
  // ADR-027: each fetched page belongs to its own server suggestion; an
  // acceptance must target the selected page's suggestion, not page 1's.
  pageSuggestionIds: string[];
  pageIndex: number;
  selectedItemId: string | null;
  loadingMore: boolean;
  moreError: string | null;
  savedToKb: boolean;
}

export interface PolishApi {
  card: PolishCardState | null;
  onCardMouseEnter: () => void;
  onCardMouseLeave: () => void;
  selectItem: (itemId: string) => void;
  acceptSelected: () => void;
  nextPage: () => void;
  prevPage: () => void;
  addSelectedToKb: () => void;
}

function dispatchMeta(editor: Editor, meta: PolishMeta) {
  editor.view.dispatch(editor.state.tr.setMeta(polishPluginKey, meta));
}

export function usePolish({
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
}): PolishApi {
  const queryClient = useQueryClient();
  const enabled = Boolean(session?.enabled_features.expression_recommendations);
  const [card, setCard] = useState<PolishCardState | null>(null);

  const editorRef = useRef<Editor | null>(editor);
  const autosaveRef = useRef(autosave);
  const sessionRef = useRef(session);
  const enabledRef = useRef(enabled);
  const applyContentRef = useRef(applyContent);
  const cardRef = useRef<PolishCardState | null>(card);
  const graceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastScanRef = useRef<string | null>(null);
  const scanningRef = useRef(false);
  // ADR-027: a sentence completed while a scan is in flight must not be
  // dropped — queue the latest span and run it when the scan finishes.
  const pendingScanRef = useRef<{ start: number; end: number; text: string } | null>(null);
  const runScanRef = useRef<((span: { start: number; end: number; text: string }) => Promise<void>) | null>(null);

  useEffect(() => {
    editorRef.current = editor;
    autosaveRef.current = autosave;
    sessionRef.current = session;
    enabledRef.current = enabled;
    applyContentRef.current = applyContent;
    cardRef.current = card;
  });

  const setCardState = useCallback((next: PolishCardState | null) => {
    cardRef.current = next;
    setCard(next);
  }, []);

  const patchCard = useCallback(
    (suggestionId: string, patch: Partial<PolishCardState>) => {
      const current = cardRef.current;
      if (!current || current.suggestionId !== suggestionId) {
        return;
      }
      setCardState({ ...current, ...patch });
    },
    [setCardState],
  );

  // --- Scanning --------------------------------------------------------------

  const runScan = useCallback(
    async (span: { start: number; end: number; text: string }) => {
      const current = editorRef.current;
      const currentSession = sessionRef.current;
      const save = autosaveRef.current;
      if (!current || !currentSession || !enabledRef.current || save.status !== "saved") {
        return;
      }
      if (scanningRef.current) {
        pendingScanRef.current = span;
        return;
      }
      scanningRef.current = true;
      try {
        const response = await polishSentence(essayId, {
          session_id: currentSession.id,
          server_revision: save.serverRevision,
          client_revision: save.clientRevision,
          sentence: span.text,
          sentence_range: {
            start: span.start,
            end: span.end,
            offset_unit: "unicode_codepoint",
          },
          paragraph_context: span.text,
        });
        const latest = editorRef.current;
        if (!latest) {
          return;
        }
        const plainNow = latest.getText({ blockSeparator: BLOCK_SEPARATOR });
        if (plainNow.slice(span.start, span.end) !== span.text) {
          return; // sentence changed while scanning; next edit re-triggers
        }
        const pmRange = codepointRangeToPm(latest.state.doc, span.start, span.end);
        if (!pmRange) {
          return;
        }
        const states: PolishFragmentState[] = [];
        for (const fragment of response.data.fragments) {
          const range = codepointRangeToPm(
            latest.state.doc,
            fragment.start_offset,
            fragment.end_offset,
          );
          if (range) {
            states.push({ fragment, from: range.from, to: range.to });
          }
        }
        const kept = getPolishFragments(latest.view).filter(
          (item) => item.to <= pmRange.from || item.from >= pmRange.to,
        );
        dispatchMeta(latest, { type: "set", fragments: [...kept, ...states] });
      } catch {
        // network / 403 / 409 / quota: editor stays usable, no underline
      } finally {
        scanningRef.current = false;
        const pending = pendingScanRef.current;
        pendingScanRef.current = null;
        if (pending) {
          void runScanRef.current?.(pending);
        }
      }
    },
    [essayId],
  );

  useEffect(() => {
    runScanRef.current = runScan;
  }, [runScan]);

  const scheduleScan = useCallback(() => {
    const current = editorRef.current;
    if (!current || !enabledRef.current) {
      return;
    }
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    // ADR-027: sentence-completion fast path; short debounce otherwise.
    const plainNow = current.getText({ blockSeparator: BLOCK_SEPARATOR });
    const cursorNow = pmRangeToCodepoints(
      current.state.doc,
      current.state.selection.from,
      current.state.selection.from,
    ).start;
    const beforeCursor = plainNow.slice(0, codepointToUtf16(plainNow, cursorNow));
    const justCompleted = /[.!?]["')\u201d\u2019]*[ \t]*$/.test(beforeCursor);
    timerRef.current = setTimeout(() => {
      const save = autosaveRef.current;
      if (save.status !== "saved") {
        return;
      }
      const plainText = current.getText({ blockSeparator: BLOCK_SEPARATOR });
      const cursorCp = pmRangeToCodepoints(
        current.state.doc,
        current.state.selection.from,
        current.state.selection.from,
      ).start;
      const spans = splitSentences(plainText);
      let span = spans.find((s) => s.complete && cursorCp >= s.start && cursorCp <= s.end);
      if (!span) {
        const before = spans.filter((s) => s.complete && s.end <= cursorCp);
        span = before[before.length - 1];
      }
      if (!span || span.text.trim() === "") {
        return;
      }
      const key = `${span.start}:${span.end}:${span.text}`;
      if (lastScanRef.current === key) {
        return;
      }
      lastScanRef.current = key;
      void runScan(span);
    }, justCompleted ? 150 : 400);
  }, [runScan]);

  useEffect(() => {
    if (!enabled || autosave.status !== "saved") {
      return;
    }
    const timer = setTimeout(() => scheduleScan(), 120);
    return () => clearTimeout(timer);
  }, [enabled, autosave.status, autosave.serverRevision, scheduleScan]);

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
        return;
      }
      // Drop fragments whose anchor text was edited (options are stale).
      const fragments = getPolishFragments(current.view);
      for (const item of fragments) {
        const anchorNow = current.state.doc.textBetween(item.from, item.to);
        if (anchorNow !== item.fragment.anchor_text) {
          dispatchMeta(current, { type: "remove", suggestionId: item.fragment.suggestion_id });
          if (cardRef.current?.suggestionId === item.fragment.suggestion_id) {
            setCardState(null);
          }
        }
      }
      scheduleScan();
    };
    const onCompositionEnd = () => scheduleScan();
    editor.on("update", onUpdate);
    editor.view.dom.addEventListener("compositionend", onCompositionEnd);
    return () => {
      editor.off("update", onUpdate);
      editor.view.dom.removeEventListener("compositionend", onCompositionEnd);
    };
  }, [editor, scheduleScan, setCardState]);

  // --- Hover / card ----------------------------------------------------------

  useEffect(() => {
    const onHover = (event: Event) => {
      const detail = (event as CustomEvent).detail as {
        suggestionId: string;
        top: number;
        left: number;
      };
      const current = editorRef.current;
      if (!current) {
        return;
      }
      const item = getPolishFragments(current.view).find(
        (f) => f.fragment.suggestion_id === detail.suggestionId,
      );
      if (!item) {
        return;
      }
      if (graceRef.current) {
        clearTimeout(graceRef.current);
        graceRef.current = null;
      }
      const existing = cardRef.current;
      if (existing && existing.suggestionId === detail.suggestionId) {
        setCardState({ ...existing, top: detail.top, left: detail.left });
        return;
      }
      setCardState({
        suggestionId: detail.suggestionId,
        top: detail.top,
        left: detail.left,
        fragment: item.fragment,
        pages: [item.fragment.items],
        pageSuggestionIds: [item.fragment.suggestion_id],
        pageIndex: 0,
        selectedItemId: item.fragment.items[0]?.id ?? null,
        loadingMore: false,
        moreError: null,
        savedToKb: false,
      });
    };
    const onHoverEnd = () => {
      if (graceRef.current) {
        clearTimeout(graceRef.current);
      }
      graceRef.current = setTimeout(() => setCardState(null), 260);
    };
    document.addEventListener(POLISH_EVENTS.hover, onHover);
    document.addEventListener(POLISH_EVENTS.hoverEnd, onHoverEnd);
    return () => {
      document.removeEventListener(POLISH_EVENTS.hover, onHover);
      document.removeEventListener(POLISH_EVENTS.hoverEnd, onHoverEnd);
    };
  }, [setCardState]);

  const onCardMouseEnter = useCallback(() => {
    if (graceRef.current) {
      clearTimeout(graceRef.current);
      graceRef.current = null;
    }
  }, []);

  const onCardMouseLeave = useCallback(() => {
    if (graceRef.current) {
      clearTimeout(graceRef.current);
    }
    graceRef.current = setTimeout(() => setCardState(null), 200);
  }, [setCardState]);

  const selectItem = useCallback(
    (itemId: string) => {
      const current = cardRef.current;
      if (current) {
        patchCard(current.suggestionId, { selectedItemId: itemId, savedToKb: false });
      }
    },
    [patchCard],
  );

  // --- Accept ----------------------------------------------------------------

  const acceptSelected = useCallback(() => {
    const current = editorRef.current;
    const state = cardRef.current;
    const save = autosaveRef.current;
    if (!current || !state || !state.selectedItemId || save.status !== "saved") {
      return;
    }
    const item = state.pages.flat().find((option) => option.id === state.selectedItemId);
    const fragmentState = getPolishFragments(current.view).find(
      (f) => f.fragment.suggestion_id === state.suggestionId,
    );
    if (!item || !fragmentState) {
      return;
    }
    const tr = current.state.tr.insertText(item.english_text, fragmentState.from, fragmentState.to);
    const newDoc = tr.doc;
    const contentJson = newDoc.toJSON() as TipTapDocument;
    const plainText = newDoc.textBetween(0, newDoc.content.size, BLOCK_SEPARATOR);
    const range = pmRangeToCodepoints(current.state.doc, fragmentState.from, fragmentState.to);
    const suggestionId = state.pageSuggestionIds[state.pageIndex] ?? state.suggestionId;
    void acceptExpressionSuggestion(essayId, suggestionId, {
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
        const latest = editorRef.current;
        if (latest) {
          dispatchMeta(latest, { type: "remove", suggestionId: state.suggestionId });
        }
        setCardState(null);
        lastScanRef.current = null;
        void queryClient.invalidateQueries({ queryKey: ["essay", essayId] });
      })
      .catch((error) => {
        // ADR-027: stale/conflicted acceptance self-heals via a fresh scan.
        if (error instanceof ApiClientError && error.status === 409) {
          setCardState(null);
          lastScanRef.current = null;
          scheduleScan();
        }
      });
  }, [essayId, setCardState, queryClient, scheduleScan]);

  // Tab accepts the selected option while the card is open; Esc closes.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const state = cardRef.current;
      if (!state) {
        return;
      }
      if (event.key === "Tab" && state.selectedItemId) {
        event.preventDefault();
        event.stopPropagation();
        acceptSelected();
      } else if (event.key === "Escape") {
        setCardState(null);
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [acceptSelected, setCardState]);

  // --- Pagination --------------------------------------------------------------

  const nextPage = useCallback(() => {
    const state = cardRef.current;
    const currentSession = sessionRef.current;
    const save = autosaveRef.current;
    const current = editorRef.current;
    if (!state || !currentSession || !current) {
      return;
    }
    if (state.pageIndex < state.pages.length - 1) {
      const targetPage = state.pages[state.pageIndex + 1];
      patchCard(state.suggestionId, {
        pageIndex: state.pageIndex + 1,
        selectedItemId: targetPage[0]?.id ?? null,
        savedToKb: false,
      });
      return;
    }
    if (state.loadingMore) {
      return;
    }
    patchCard(state.suggestionId, { loadingMore: true, moreError: null });
    const exclude = state.pages.flat().map((option) => option.english_text);
    const fragmentState = getPolishFragments(current.view).find(
      (f) => f.fragment.suggestion_id === state.suggestionId,
    );
    const sentence = fragmentState
      ? current.state.doc.textBetween(
          Math.max(0, fragmentState.from - 200),
          Math.min(current.state.doc.content.size, fragmentState.to + 200),
        )
      : state.fragment.anchor_text;
    void polishSentence(essayId, {
      session_id: currentSession.id,
      server_revision: save.serverRevision,
      client_revision: save.clientRevision,
      sentence,
      sentence_range: { start: 0, end: sentence.length, offset_unit: "unicode_codepoint" },
      fragment_anchor: state.fragment.anchor_text,
      exclude,
    })
      .then((response) => {
        const match = response.data.fragments.find(
          (f) => f.anchor_text === state.fragment.anchor_text,
        );
        const latest = cardRef.current;
        if (!latest || latest.suggestionId !== state.suggestionId) {
          return;
        }
        if (match && match.items.length > 0) {
          patchCard(state.suggestionId, {
            pages: [...latest.pages, match.items],
            pageSuggestionIds: [...latest.pageSuggestionIds, match.suggestion_id],
            pageIndex: latest.pages.length,
            selectedItemId: match.items[0].id,
            loadingMore: false,
          });
        } else {
          patchCard(state.suggestionId, {
            loadingMore: false,
            moreError: "没有更多不同的表达了。",
          });
        }
      })
      .catch(() => {
        patchCard(state.suggestionId, { loadingMore: false, moreError: "获取更多表达失败。" });
      });
  }, [essayId, patchCard]);

  const prevPage = useCallback(() => {
    const state = cardRef.current;
    if (state && state.pageIndex > 0) {
      const targetPage = state.pages[state.pageIndex - 1];
      patchCard(state.suggestionId, {
        pageIndex: state.pageIndex - 1,
        selectedItemId: targetPage[0]?.id ?? null,
        savedToKb: false,
      });
    }
  }, [patchCard]);

  // --- Knowledge base ----------------------------------------------------------

  const addSelectedToKb = useCallback(() => {
    const state = cardRef.current;
    if (!state || !state.selectedItemId) {
      return;
    }
    const item = state.pages.flat().find((option) => option.id === state.selectedItemId);
    if (!item) {
      return;
    }
    void createExpression({
      english_text: item.english_text,
      chinese_meaning: item.chinese_meaning,
      usage_context: item.usage_note,
      register: item.register,
      source_type: "suggestion",
      essay_id: essayId,
      source_context: state.fragment.anchor_text,
    })
      .then(() => {
        patchCard(state.suggestionId, { savedToKb: true });
        void queryClient.invalidateQueries({ queryKey: ["expressions"] });
      })
      .catch(() => {
        patchCard(state.suggestionId, { moreError: "加入知识库失败（可能已存在）。" });
      });
  }, [essayId, patchCard, queryClient]);

  return {
    card,
    onCardMouseEnter,
    onCardMouseLeave,
    selectItem,
    acceptSelected,
    nextPage,
    prevPage,
    addSelectedToKb,
  };
}
