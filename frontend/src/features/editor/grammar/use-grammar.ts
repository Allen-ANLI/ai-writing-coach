"use client";

/**
 * 语法编排（ADR-024，取代 ADR-016 的模糊/揭示/点击教学交互）：
 * - 句子完成时自动检查（防抖 + 过期请求取消），无手动检查按钮。
 * - 悬浮错误即显示卡片：并行拉取修改建议（reveal）与详细讲解（teaching，
 *   服务端按 issue+revision+context 缓存，前端按 issue 缓存）。
 * - 卡片可见时 Tab 接受推荐修改；Esc 关闭；Alt+I 忽略。
 * - 保存后验证用户自改；规则优先在后端执行，本层不直接调用 LLM。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { useQueryClient } from "@tanstack/react-query";

import {
  GRAMMAR_EVENTS,
  grammarPluginKey,
  getGrammarIssues,
  type GrammarIssueState,
  type GrammarMeta,
} from "@/features/editor/grammar/grammar-extension";
import type { HoverCardState } from "@/features/editor/grammar/grammar-hover-card";
import type { AutosaveApi } from "@/features/editor/use-autosave";
import { ApiClientError } from "@/lib/api-client";
import { BLOCK_SEPARATOR, splitSentences } from "@/lib/document-text";
import {
  codepointRangeToPm,
  pmRangeToCodepoints,
} from "@/lib/text-positions";
import {
  acceptIssue,
  getIssue,
  grammarCheck,
  ignoreIssue,
  requestTeaching,
  revealIssue,
  validateIssue,
} from "@/services/grammar";
import type {
  IssueData,
  SessionData,
  TeachingData,
  TipTapDocument,
} from "@/types/api";

export interface GrammarApi {
  issueCount: number;
  hoverCard: HoverCardState | null;
  onCardMouseEnter: () => void;
  onCardMouseLeave: () => void;
  acceptCorrection: () => void;
  ignoreFromCard: () => void;
  retryTeaching: () => void;
}

function dispatchMeta(editor: Editor, meta: GrammarMeta) {
  editor.view.dispatch(editor.state.tr.setMeta(grammarPluginKey, meta));
}

function toIssueStates(editor: Editor, issues: IssueData[]): GrammarIssueState[] {
  const states: GrammarIssueState[] = [];
  for (const issue of issues) {
    const range = codepointRangeToPm(editor.state.doc, issue.start_offset, issue.end_offset);
    if (!range) {
      continue; // unreliable mapping: drop, never apply old offsets blindly
    }
    states.push({ issue, from: range.from, to: range.to, revealed: null });
  }
  return states;
}

function teachingErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    if (error.status === 409) {
      return "文档已更新，请关闭卡片后重新悬浮查看讲解。";
    }
    if (error.status === 429) {
      return "AI 额度已用完或请求过于频繁，请稍后再试。";
    }
    if (error.status === 502 || error.status === 504) {
      return "AI 服务暂时不可用，请稍后重试。";
    }
    return error.message;
  }
  return "详细讲解暂时不可用，请稍后重试。";
}

export function useGrammar({
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
}): GrammarApi {
  const queryClient = useQueryClient();
  const enabled = Boolean(session?.enabled_features.realtime_grammar);
  const [issueCount, setIssueCount] = useState(0);
  const [hoverCard, setHoverCard] = useState<HoverCardState | null>(null);

  const editorRef = useRef<Editor | null>(editor);
  const autosaveRef = useRef(autosave);
  const sessionRef = useRef(session);
  const enabledRef = useRef(enabled);
  const applyContentRef = useRef(applyContent);
  const hoverRef = useRef<HoverCardState | null>(null);
  const hoverGraceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const checkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pendingValidationRef = useRef<Map<string, { start: number; end: number }>>(new Map());
  const validatingRef = useRef(false);
  const teachingCacheRef = useRef<Map<string, TeachingData>>(new Map());
  const teachingPendingRef = useRef<Set<string>>(new Set());
  // ADR-025: skip re-checking an unchanged sentence while the user types the
  // next one (server-side cache also prevents duplicate LLM spend).
  const lastCheckedRef = useRef<string | null>(null);

  useEffect(() => {
    editorRef.current = editor;
    autosaveRef.current = autosave;
    sessionRef.current = session;
    enabledRef.current = enabled;
    applyContentRef.current = applyContent;
    hoverRef.current = hoverCard;
  });

  const syncCount = useCallback(() => {
    const current = editorRef.current;
    setIssueCount(current ? getGrammarIssues(current.view).length : 0);
  }, []);

  const setHover = useCallback((next: HoverCardState | null) => {
    hoverRef.current = next;
    setHoverCard(next);
  }, []);

  const patchHover = useCallback(
    (issueId: string, patch: Partial<HoverCardState>) => {
      const current = hoverRef.current;
      if (!current || current.issueId !== issueId) {
        return;
      }
      setHover({ ...current, ...patch });
    },
    [setHover],
  );

  // --- Checking -------------------------------------------------------------

  const runCheck = useCallback(
    async (span: { start: number; end: number; text: string }) => {
      const current = editorRef.current;
      const currentSession = sessionRef.current;
      const save = autosaveRef.current;
      if (!current || !currentSession || !enabledRef.current || save.status !== "saved") {
        return;
      }
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const revisionAtRequest = save.serverRevision;
      try {
        const response = await grammarCheck(
          essayId,
          {
            session_id: currentSession.id,
            server_revision: revisionAtRequest,
            client_revision: save.clientRevision,
            text: span.text,
            text_range: {
              start: span.start,
              end: span.end,
              offset_unit: "unicode_codepoint",
            },
            context: { paragraph_text: span.text },
          },
          controller.signal,
        );
        if (controller.signal.aborted) {
          return;
        }
        const latest = editorRef.current;
        if (!latest) {
          return;
        }
        // ADR-025 stale reconciliation: autosave may bump the revision while
        // the check runs. Apply the findings when the checked sentence is
        // still verbatim at the same range (offsets remain valid); otherwise
        // drop — the saved-effect re-schedules at the new revision.
        const plainNow = latest.getText({ blockSeparator: BLOCK_SEPARATOR });
        const rangeIntact = plainNow.slice(span.start, span.end) === span.text;
        if (
          response.data.server_revision !== autosaveRef.current.serverRevision &&
          !rangeIntact
        ) {
          return;
        }
        const pmRange = codepointRangeToPm(latest.state.doc, span.start, span.end);
        if (!pmRange) {
          return;
        }
        dispatchMeta(latest, {
          type: "merge",
          start: pmRange.from,
          end: pmRange.to,
          issues: toIssueStates(latest, response.data.issues),
        });
        syncCount();
      } catch {
        // aborted / 403 independent / 409 stale / network: editor stays usable
      }
    },
    [essayId, syncCount],
  );

  const scheduleCheckForEdit = useCallback(() => {
    const current = editorRef.current;
    if (!current || !enabledRef.current) {
      return;
    }
    if (checkTimerRef.current) {
      clearTimeout(checkTimerRef.current);
    }
    checkTimerRef.current = setTimeout(() => {
      const save = autosaveRef.current;
      if (save.status !== "saved") {
        return; // wait for the save; the saved-effect re-triggers
      }
      const plainText = current.getText({ blockSeparator: BLOCK_SEPARATOR });
      const cursorCp = pmRangeToCodepoints(
        current.state.doc,
        current.state.selection.from,
        current.state.selection.from,
      ).start;
      const spans = splitSentences(plainText);
      // ADR-025: check the completed sentence at the cursor, or the last
      // completed sentence BEFORE the cursor — fast typists move past the
      // period before the debounce fires, which used to skip checks entirely.
      let span = spans.find(
        (s) => s.complete && cursorCp >= s.start && cursorCp <= s.end,
      );
      if (!span) {
        const before = spans.filter((s) => s.complete && s.end <= cursorCp);
        span = before[before.length - 1];
      }
      if (!span || span.text.trim() === "") {
        return; // never check incomplete input prematurely
      }
      const key = `${span.start}:${span.end}:${span.text}`;
      if (lastCheckedRef.current === key) {
        return; // unchanged sentence already checked
      }
      lastCheckedRef.current = key;
      void runCheck(span);
    }, 900);
  }, [runCheck]);

  // --- Self-correction validation -------------------------------------------

  const runValidations = useCallback(async () => {
    const current = editorRef.current;
    if (!current || validatingRef.current || pendingValidationRef.current.size === 0) {
      return;
    }
    if (autosaveRef.current.status !== "saved") {
      return;
    }
    validatingRef.current = true;
    try {
      for (const [issueId, range] of Array.from(pendingValidationRef.current.entries())) {
        pendingValidationRef.current.delete(issueId);
        const existing = getGrammarIssues(current.view).find((i) => i.issue.id === issueId);
        if (!existing) {
          continue;
        }
        const contentJson = current.getJSON() as TipTapDocument;
        const plainText = current.getText({ blockSeparator: BLOCK_SEPARATOR });
        try {
          const response = await validateIssue(essayId, {
            issue_id: issueId,
            base_revision: autosaveRef.current.serverRevision,
            client_revision: autosaveRef.current.clientRevision,
            content_json: contentJson,
            plain_text: plainText,
            word_count: plainText.match(/\S+/g)?.length ?? 0,
            modified_range: { ...range, offset_unit: "unicode_codepoint" },
          });
          autosaveRef.current.setServerRevision(response.data.server_revision);
          if (response.data.is_resolved) {
            dispatchMeta(current, { type: "remove", issueId });
          } else {
            const refreshed = await getIssue(essayId, issueId);
            const [state] = toIssueStates(current, [refreshed.data]);
            if (state) {
              dispatchMeta(current, { type: "update", issueId, state });
            }
          }
        } catch (error) {
          if (error instanceof ApiClientError && error.status === 409) {
            scheduleCheckForEdit();
          }
        }
      }
    } finally {
      validatingRef.current = false;
      syncCount();
    }
  }, [essayId, syncCount, scheduleCheckForEdit]);

  // After each successful save: validate edited issues, then check completed
  // sentences at the new revision.
  useEffect(() => {
    if (!enabled || autosave.status !== "saved") {
      return;
    }
    const timer = setTimeout(() => {
      void runValidations().then(() => scheduleCheckForEdit());
    }, 300);
    return () => clearTimeout(timer);
  }, [enabled, autosave.status, autosave.serverRevision, runValidations, scheduleCheckForEdit]);

  // Track edits: schedule sentence checks + mark intersected issues pending.
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
        return; // IME composition: wait for compositionend
      }
      scheduleCheckForEdit();
      const issues = getGrammarIssues(current.view);
      if (issues.length === 0) {
        return;
      }
      for (const map of transaction.mapping.maps) {
        map.forEach((_oldStart, _oldEnd, newStart, newEnd) => {
          for (const item of issues) {
            if (newStart <= item.to && newEnd >= item.from) {
              const cp = pmRangeToCodepoints(current.state.doc, item.from, item.to);
              pendingValidationRef.current.set(item.issue.id, cp);
            }
          }
        });
      }
    };
    const onCompositionEnd = () => scheduleCheckForEdit();
    editor.on("update", onUpdate);
    editor.view.dom.addEventListener("compositionend", onCompositionEnd);
    return () => {
      editor.off("update", onUpdate);
      editor.view.dom.removeEventListener("compositionend", onCompositionEnd);
    };
  }, [editor, scheduleCheckForEdit]);

  // --- Hover: fetch suggestions + teaching in parallel -----------------------

  const loadSuggestions = useCallback(
    (item: GrammarIssueState) => {
      const current = editorRef.current;
      if (!current) {
        return;
      }
      if (item.revealed) {
        patchHover(item.issue.id, { suggestions: item.revealed, suggestionsLoading: false });
        return;
      }
      patchHover(item.issue.id, { suggestionsLoading: true });
      void revealIssue(essayId, item.issue.id)
        .then((response) => {
          dispatchMeta(current, {
            type: "reveal",
            issueId: item.issue.id,
            suggestions: response.data.suggestions,
          });
          patchHover(item.issue.id, {
            suggestions: response.data.suggestions,
            suggestionsLoading: false,
          });
        })
        .catch(() => patchHover(item.issue.id, { suggestionsLoading: false }));
    },
    [essayId, patchHover],
  );

  const loadTeaching = useCallback(
    (item: GrammarIssueState, force = false) => {
      const current = editorRef.current;
      if (!current) {
        return;
      }
      const issueId = item.issue.id;
      const cached = teachingCacheRef.current.get(issueId);
      if (cached && !force) {
        patchHover(issueId, { teaching: cached, teachingLoading: false, teachingError: null });
        return;
      }
      if (teachingPendingRef.current.has(issueId)) {
        return;
      }
      teachingPendingRef.current.add(issueId);
      patchHover(issueId, { teachingLoading: true, teachingError: null });

      const plainText = current.getText({ blockSeparator: BLOCK_SEPARATOR });
      const cp = pmRangeToCodepoints(current.state.doc, item.from, item.from).start;
      const spans = splitSentences(plainText);
      const span = spans.find((s) => cp >= s.start && cp <= s.end);
      const sentence = span?.text ?? plainText;
      void requestTeaching(essayId, issueId, {
        server_revision: autosaveRef.current.serverRevision,
        client_revision: autosaveRef.current.clientRevision,
        current_sentence: sentence,
        paragraph_context: sentence,
        user_current_text: current.state.doc.textBetween(item.from, item.to),
      })
        .then((response) => {
          teachingCacheRef.current.set(issueId, response.data);
          patchHover(issueId, {
            teaching: response.data,
            teachingLoading: false,
            teachingError: null,
          });
        })
        .catch((error) => {
          patchHover(issueId, {
            teachingLoading: false,
            teachingError: teachingErrorMessage(error),
          });
        })
        .finally(() => {
          teachingPendingRef.current.delete(issueId);
        });
    },
    [essayId, patchHover],
  );

  useEffect(() => {
    const onHover = (event: Event) => {
      const detail = (event as CustomEvent).detail as {
        issueId: string;
        top: number;
        left: number;
      };
      const current = editorRef.current;
      if (!current) {
        return;
      }
      const item = getGrammarIssues(current.view).find((i) => i.issue.id === detail.issueId);
      if (!item) {
        return;
      }
      if (hoverGraceRef.current) {
        clearTimeout(hoverGraceRef.current);
        hoverGraceRef.current = null;
      }
      const existing = hoverRef.current;
      if (existing && existing.issueId === detail.issueId) {
        // Same issue: keep loaded content, just follow the anchor position.
        setHover({ ...existing, top: detail.top, left: detail.left });
        return;
      }
      const cachedTeaching = teachingCacheRef.current.get(item.issue.id) ?? null;
      setHover({
        issueId: detail.issueId,
        top: detail.top,
        left: detail.left,
        explanation: item.issue.short_explanation,
        suggestions: item.revealed,
        suggestionsLoading: !item.revealed,
        teaching: cachedTeaching,
        teachingLoading: !cachedTeaching,
        teachingError: null,
      });
      loadSuggestions(item);
      loadTeaching(item);
    };
    const onHoverEnd = () => {
      if (hoverGraceRef.current) {
        clearTimeout(hoverGraceRef.current);
      }
      hoverGraceRef.current = setTimeout(() => setHover(null), 260);
    };
    document.addEventListener(GRAMMAR_EVENTS.hover, onHover);
    document.addEventListener(GRAMMAR_EVENTS.hoverEnd, onHoverEnd);
    return () => {
      document.removeEventListener(GRAMMAR_EVENTS.hover, onHover);
      document.removeEventListener(GRAMMAR_EVENTS.hoverEnd, onHoverEnd);
    };
  }, [setHover, loadSuggestions, loadTeaching]);

  const onCardMouseEnter = useCallback(() => {
    if (hoverGraceRef.current) {
      clearTimeout(hoverGraceRef.current);
      hoverGraceRef.current = null;
    }
  }, []);

  const onCardMouseLeave = useCallback(() => {
    if (hoverGraceRef.current) {
      clearTimeout(hoverGraceRef.current);
    }
    hoverGraceRef.current = setTimeout(() => setHover(null), 200);
  }, [setHover]);

  // --- Accept / ignore --------------------------------------------------------

  const acceptCorrection = useCallback(() => {
    const current = editorRef.current;
    const card = hoverRef.current;
    if (!current || !card || !card.suggestions || card.suggestions.length === 0) {
      return;
    }
    const save = autosaveRef.current;
    const recommended = card.suggestions.find((s) => s.is_recommended) ?? card.suggestions[0];
    void acceptIssue(essayId, card.issueId, {
      base_revision: save.serverRevision,
      client_revision: save.clientRevision,
      suggestion_id: recommended?.id ?? null,
    })
      .then((response) => {
        applyContentRef.current(response.data.content_json);
        autosaveRef.current.setServerRevision(response.data.server_revision);
        dispatchMeta(current, { type: "remove", issueId: card.issueId });
        setHover(null);
        syncCount();
        void queryClient.invalidateQueries({ queryKey: ["essay", essayId] });
      })
      .catch(() => undefined);
  }, [essayId, setHover, syncCount, queryClient]);

  const ignore = useCallback(
    (issueId: string) => {
      const current = editorRef.current;
      if (!current) {
        return;
      }
      void ignoreIssue(essayId, issueId)
        .then(() => {
          dispatchMeta(current, { type: "remove", issueId });
          if (hoverRef.current?.issueId === issueId) {
            setHover(null);
          }
          syncCount();
        })
        .catch(() => undefined);
    },
    [essayId, setHover, syncCount],
  );

  const ignoreFromCard = useCallback(() => {
    const card = hoverRef.current;
    if (card) {
      ignore(card.issueId);
    }
  }, [ignore]);

  const retryTeaching = useCallback(() => {
    const current = editorRef.current;
    const card = hoverRef.current;
    if (!current || !card) {
      return;
    }
    const item = getGrammarIssues(current.view).find((i) => i.issue.id === card.issueId);
    if (item) {
      loadTeaching(item, true);
    }
  }, [loadTeaching]);

  // Tab accepts while the card is visible with a suggestion; Esc closes.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const card = hoverRef.current;
      if (!card) {
        return;
      }
      if (event.key === "Tab" && card.suggestions && card.suggestions.length > 0) {
        event.preventDefault();
        event.stopPropagation();
        acceptCorrection();
      } else if (event.key === "Escape") {
        setHover(null);
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [acceptCorrection, setHover]);

  // Alt+I ignores the issue at the caret or under the card.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const current = editorRef.current;
      if (!current || event.key.toLowerCase() !== "i") {
        return;
      }
      const pos = current.state.selection.from;
      const item =
        getGrammarIssues(current.view).find((i) => pos >= i.from && pos <= i.to) ??
        getGrammarIssues(current.view).find((i) => i.issue.id === hoverRef.current?.issueId);
      if (item) {
        event.preventDefault();
        ignore(item.issue.id);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [ignore]);

  // Bridge the extension's ignore event (kept for programmatic callers).
  useEffect(() => {
    const onIgnore = (event: Event) => ignore((event as CustomEvent).detail.issueId);
    document.addEventListener(GRAMMAR_EVENTS.ignore, onIgnore);
    return () => document.removeEventListener(GRAMMAR_EVENTS.ignore, onIgnore);
  }, [ignore]);

  return {
    issueCount,
    hoverCard,
    onCardMouseEnter,
    onCardMouseLeave,
    acceptCorrection,
    ignoreFromCard,
    retryTeaching,
  };
}
