"use client";

/**
 * Grammar orchestration (finalized UX, user decision 2026-11-15):
 * - Automatic checks when a sentence is COMPLETED (punctuation/paragraph
 *   break), debounced, with stale-request cancellation. No manual check button.
 * - Hover feedback card; clicking the blurred answer reveals and pins it;
 *   Tab accepts the correction ONLY while pinned (normal Tab otherwise).
 * - Self-correction validation after saves; teaching via the small icon.
 * - Rule-first on the backend; this layer never calls an LLM directly.
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
import type { IssueData, SessionData, TeachingData, TipTapDocument } from "@/types/api";

export interface TeachingState {
  issueId: string;
  loading: boolean;
  error: string | null;
  data: TeachingData | null;
  top: number;
  left: number;
}

export interface GrammarApi {
  issueCount: number;
  hoverCard: HoverCardState | null;
  onCardMouseEnter: () => void;
  onCardMouseLeave: () => void;
  revealAnswer: () => void;
  teachFromCard: () => void;
  teaching: TeachingState | null;
  closeTeaching: () => void;
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
  const [teaching, setTeaching] = useState<TeachingState | null>(null);

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
        // Stale-response guard: document moved on while the check ran.
        if (
          controller.signal.aborted ||
          response.data.server_revision !== autosaveRef.current.serverRevision
        ) {
          return;
        }
        dispatchMeta(current, {
          type: "set",
          issues: toIssueStates(current, response.data.issues),
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
      const span = spans.find((s) => cursorCp >= s.start && cursorCp <= s.end);
      if (!span || !span.complete || span.text.trim() === "") {
        return; // never check incomplete input prematurely
      }
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

  // --- Hover / reveal / accept ----------------------------------------------

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
      const pinned = existing?.pinned && existing.issueId === detail.issueId;
      setHover({
        issueId: detail.issueId,
        top: detail.top,
        left: detail.left,
        explanation: item.issue.short_explanation,
        revealed: pinned ? existing.revealed : item.revealed,
        pinned: Boolean(pinned),
      });
    };
    const onHoverEnd = () => {
      if (hoverRef.current?.pinned) {
        return; // pinned correction stays until Tab/Esc
      }
      if (hoverGraceRef.current) {
        clearTimeout(hoverGraceRef.current);
      }
      hoverGraceRef.current = setTimeout(() => {
        if (!hoverRef.current?.pinned) {
          setHover(null);
        }
      }, 260);
    };
    document.addEventListener(GRAMMAR_EVENTS.hover, onHover);
    document.addEventListener(GRAMMAR_EVENTS.hoverEnd, onHoverEnd);
    return () => {
      document.removeEventListener(GRAMMAR_EVENTS.hover, onHover);
      document.removeEventListener(GRAMMAR_EVENTS.hoverEnd, onHoverEnd);
    };
  }, [setHover]);

  const onCardMouseEnter = useCallback(() => {
    if (hoverGraceRef.current) {
      clearTimeout(hoverGraceRef.current);
      hoverGraceRef.current = null;
    }
  }, []);

  const onCardMouseLeave = useCallback(() => {
    if (hoverRef.current?.pinned) {
      return;
    }
    if (hoverGraceRef.current) {
      clearTimeout(hoverGraceRef.current);
    }
    hoverGraceRef.current = setTimeout(() => setHover(null), 200);
  }, [setHover]);

  const revealAnswer = useCallback(() => {
    const current = editorRef.current;
    const card = hoverRef.current;
    if (!current || !card) {
      return;
    }
    void revealIssue(essayId, card.issueId)
      .then((response) => {
        dispatchMeta(current, {
          type: "reveal",
          issueId: card.issueId,
          suggestions: response.data.suggestions,
        });
        setHover({
          ...card,
          revealed: response.data.suggestions,
          pinned: true,
        });
      })
      .catch(() => undefined);
  }, [essayId, setHover]);

  const acceptPinned = useCallback(() => {
    const current = editorRef.current;
    const card = hoverRef.current;
    if (!current || !card?.pinned || !card.revealed) {
      return;
    }
    const save = autosaveRef.current;
    const recommended = card.revealed.find((s) => s.is_recommended) ?? card.revealed[0];
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

  // Tab accepts ONLY while a revealed correction is pinned; Esc closes.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const card = hoverRef.current;
      if (event.key === "Tab" && card?.pinned && card.revealed) {
        event.preventDefault();
        event.stopPropagation();
        acceptPinned();
      } else if (event.key === "Escape" && card) {
        setHover(null);
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [acceptPinned, setHover]);

  // --- Teaching / ignore / shortcuts -----------------------------------------

  const teach = useCallback(
    (issueId: string) => {
      const current = editorRef.current;
      if (!current) {
        return;
      }
      const item = getGrammarIssues(current.view).find((i) => i.issue.id === issueId);
      if (!item) {
        return;
      }
      const coords = current.view.coordsAtPos(item.from);
      const plainText = current.getText({ blockSeparator: BLOCK_SEPARATOR });
      const cp = pmRangeToCodepoints(current.state.doc, item.from, item.from).start;
      const spans = splitSentences(plainText);
      const span = spans.find((s) => cp >= s.start && cp <= s.end);
      const sentence = span?.text ?? plainText;
      setTeaching({
        issueId,
        loading: true,
        error: null,
        data: null,
        top: Math.min(coords.bottom + 8, window.innerHeight - 320),
        left: Math.max(16, Math.min(coords.left, window.innerWidth - 420)),
      });
      void requestTeaching(essayId, issueId, {
        server_revision: autosaveRef.current.serverRevision,
        client_revision: autosaveRef.current.clientRevision,
        current_sentence: sentence,
        paragraph_context: sentence,
        user_current_text: current.state.doc.textBetween(item.from, item.to),
      })
        .then((response) => {
          setTeaching((previous) =>
            previous && previous.issueId === issueId
              ? { ...previous, loading: false, data: response.data }
              : previous,
          );
        })
        .catch((error) => {
          setTeaching((previous) =>
            previous && previous.issueId === issueId
              ? {
                  ...previous,
                  loading: false,
                  error:
                    error instanceof ApiClientError
                      ? error.message
                      : "Teaching is unavailable right now.",
                }
              : previous,
          );
        });
    },
    [essayId],
  );

  const teachFromCard = useCallback(() => {
    const card = hoverRef.current;
    if (card) {
      teach(card.issueId);
    }
  }, [teach]);

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

  const closeTeaching = useCallback(() => setTeaching(null), []);

  // Keyboard shortcuts: Alt+R reveal, Alt+T teach, Alt+I ignore (issue at caret
  // or pinned card).
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const current = editorRef.current;
      if (!current) {
        return;
      }
      const pos = current.state.selection.from;
      const item =
        getGrammarIssues(current.view).find((i) => pos >= i.from && pos <= i.to) ??
        getGrammarIssues(current.view).find((i) => i.issue.id === hoverRef.current?.issueId);
      if (!item) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "r") {
        event.preventDefault();
        void revealIssue(essayId, item.issue.id).then((response) => {
          dispatchMeta(current, {
            type: "reveal",
            issueId: item.issue.id,
            suggestions: response.data.suggestions,
          });
          const coords = current.view.coordsAtPos(item.from);
          setHover({
            issueId: item.issue.id,
            top: coords.bottom,
            left: coords.left,
            explanation: item.issue.short_explanation,
            revealed: response.data.suggestions,
            pinned: true,
          });
        });
      } else if (key === "t") {
        event.preventDefault();
        teach(item.issue.id);
      } else if (key === "i") {
        event.preventDefault();
        ignore(item.issue.id);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [essayId, teach, ignore, setHover]);

  // Bridge extension DOM events to the latest handlers.
  useEffect(() => {
    const onTeach = (event: Event) => teach((event as CustomEvent).detail.issueId);
    const onIgnore = (event: Event) => ignore((event as CustomEvent).detail.issueId);
    document.addEventListener(GRAMMAR_EVENTS.teach, onTeach);
    document.addEventListener(GRAMMAR_EVENTS.ignore, onIgnore);
    return () => {
      document.removeEventListener(GRAMMAR_EVENTS.teach, onTeach);
      document.removeEventListener(GRAMMAR_EVENTS.ignore, onIgnore);
    };
  }, [teach, ignore]);

  return {
    issueCount,
    hoverCard,
    onCardMouseEnter,
    onCardMouseLeave,
    revealAnswer,
    teachFromCard,
    teaching,
    closeTeaching,
  };
}
