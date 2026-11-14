"use client";

/**
 * Grammar orchestration: debounced checks after saves, self-correction
 * validation, reveal/ignore, contextual teaching, keyboard shortcuts.
 *
 * Coordinates with autosave: checks and validations always use the latest
 * saved server_revision; stale responses are discarded, never applied.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";

import {
  GRAMMAR_EVENTS,
  grammarPluginKey,
  getGrammarIssues,
  type GrammarIssueState,
  type GrammarMeta,
} from "@/features/editor/grammar/grammar-extension";
import type { AutosaveApi } from "@/features/editor/use-autosave";
import { ApiClientError } from "@/lib/api-client";
import { BLOCK_SEPARATOR, sentenceAround } from "@/lib/document-text";
import { codepointRangeToPm, codepointToUtf16, pmRangeToCodepoints, utf16ToCodepoint } from "@/lib/text-positions";
import {
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
  checking: boolean;
  checkNow: () => void;
  reveal: (issueId: string) => void;
  ignore: (issueId: string) => void;
  teach: (issueId: string) => void;
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
}: {
  essayId: string;
  editor: Editor | null;
  session: SessionData | null;
  autosave: AutosaveApi;
}): GrammarApi {
  const enabled = Boolean(session?.enabled_features.realtime_grammar);
  const [issueCount, setIssueCount] = useState(0);
  const [checking, setChecking] = useState(false);
  const [teaching, setTeaching] = useState<TeachingState | null>(null);

  const editorRef = useRef<Editor | null>(editor);
  const autosaveRef = useRef(autosave);
  const sessionRef = useRef(session);
  const enabledRef = useRef(enabled);
  const pendingCheckRef = useRef(false);
  const pendingValidationRef = useRef<Map<string, { start: number; end: number }>>(new Map());
  const validatingRef = useRef(false);
  const checkTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    editorRef.current = editor;
    autosaveRef.current = autosave;
    sessionRef.current = session;
    enabledRef.current = enabled;
  });

  const syncCount = useCallback(() => {
    const current = editorRef.current;
    setIssueCount(current ? getGrammarIssues(current.view).length : 0);
  }, []);

  const runCheck = useCallback(async () => {
    const current = editorRef.current;
    const currentSession = sessionRef.current;
    const save = autosaveRef.current;
    if (!current || !currentSession || !enabledRef.current) {
      return;
    }
    if (save.status !== "saved") {
      pendingCheckRef.current = true;
      save.saveNow();
      return;
    }
    const plainText = current.getText({ blockSeparator: BLOCK_SEPARATOR });
    if (plainText.trim() === "") {
      dispatchMeta(current, { type: "set", issues: [] });
      syncCount();
      return;
    }
    const cursorCp = pmRangeToCodepoints(
      current.state.doc,
      current.state.selection.from,
      current.state.selection.from,
    ).start;
    const [sentence, startU16] = sentenceAround(plainText, codepointToUtf16(plainText, cursorCp));
    if (sentence.trim() === "") {
      return;
    }
    const start = utf16ToCodepoint(plainText, startU16);
    const end = utf16ToCodepoint(plainText, startU16 + sentence.length);
    setChecking(true);
    try {
      const response = await grammarCheck(essayId, {
        session_id: currentSession.id,
        server_revision: save.serverRevision,
        client_revision: save.clientRevision,
        text: sentence,
        text_range: { start, end, offset_unit: "unicode_codepoint" },
        context: { paragraph_text: sentence },
      });
      if (response.data.server_revision !== autosaveRef.current.serverRevision) {
        return; // stale response: user kept editing; discard
      }
      dispatchMeta(current, {
        type: "set",
        issues: toIssueStates(current, response.data.issues),
      });
      syncCount();
    } catch {
      // 403 (independent mode) / 409 (stale) / network: keep the editor usable.
    } finally {
      setChecking(false);
    }
  }, [essayId, syncCount]);

  const runValidations = useCallback(async () => {
    const current = editorRef.current;
    if (!current || validatingRef.current || pendingValidationRef.current.size === 0) {
      return;
    }
    const save = autosaveRef.current;
    if (save.status !== "saved") {
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
            pendingCheckRef.current = true;
          }
        }
      }
    } finally {
      validatingRef.current = false;
      syncCount();
    }
  }, [essayId, syncCount]);

  // After each successful save: run pending validations, then a fresh check.
  useEffect(() => {
    if (!enabled || autosave.status !== "saved") {
      return;
    }
    if (checkTimerRef.current) {
      clearTimeout(checkTimerRef.current);
    }
    checkTimerRef.current = setTimeout(() => {
      void runValidations().then(() => {
        if (pendingCheckRef.current) {
          pendingCheckRef.current = false;
        }
        void runCheck();
      });
    }, 400);
    return () => {
      if (checkTimerRef.current) {
        clearTimeout(checkTimerRef.current);
      }
    };
  }, [enabled, autosave.status, autosave.serverRevision, runCheck, runValidations]);

  // Track edits intersecting issue ranges for self-correction validation.
  useEffect(() => {
    if (!editor) {
      return;
    }
    const onUpdate = ({ transaction }: { transaction: import("@tiptap/pm/state").Transaction }) => {
      if (!transaction.docChanged || !enabledRef.current) {
        return;
      }
      const current = editorRef.current;
      if (!current) {
        return;
      }
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
    editor.on("update", onUpdate);
    return () => {
      editor.off("update", onUpdate);
    };
  }, [editor]);

  const reveal = useCallback(
    (issueId: string) => {
      const current = editorRef.current;
      if (!current) {
        return;
      }
      void revealIssue(essayId, issueId)
        .then((response) => {
          dispatchMeta(current, {
            type: "reveal",
            issueId,
            suggestions: response.data.suggestions,
          });
        })
        .catch(() => undefined);
    },
    [essayId],
  );

  const ignore = useCallback(
    (issueId: string) => {
      const current = editorRef.current;
      if (!current) {
        return;
      }
      void ignoreIssue(essayId, issueId)
        .then(() => {
          dispatchMeta(current, { type: "remove", issueId });
          syncCount();
        })
        .catch(() => undefined);
    },
    [essayId, syncCount],
  );

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
      const [sentence] = sentenceAround(plainText, codepointToUtf16(plainText, cp));
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

  const closeTeaching = useCallback(() => setTeaching(null), []);

  const checkNow = useCallback(() => {
    pendingCheckRef.current = true;
    void runCheck();
  }, [runCheck]);

  // Keyboard shortcuts: Alt+R reveal, Alt+T teach, Alt+I ignore (issue at caret).
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
      const item = getGrammarIssues(current.view).find((i) => pos >= i.from && pos <= i.to);
      if (!item) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "r") {
        event.preventDefault();
        reveal(item.issue.id);
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
  }, [reveal, teach, ignore]);

  // Bridge ProseMirror widget events to the latest handlers (subscribed in an
  // effect; the extension itself stays render-phase pure).
  useEffect(() => {
    const onReveal = (event: Event) => reveal((event as CustomEvent).detail.issueId);
    const onIgnore = (event: Event) => ignore((event as CustomEvent).detail.issueId);
    const onTeach = (event: Event) => teach((event as CustomEvent).detail.issueId);
    document.addEventListener(GRAMMAR_EVENTS.reveal, onReveal);
    document.addEventListener(GRAMMAR_EVENTS.ignore, onIgnore);
    document.addEventListener(GRAMMAR_EVENTS.teach, onTeach);
    return () => {
      document.removeEventListener(GRAMMAR_EVENTS.reveal, onReveal);
      document.removeEventListener(GRAMMAR_EVENTS.ignore, onIgnore);
      document.removeEventListener(GRAMMAR_EVENTS.teach, onTeach);
    };
  }, [reveal, ignore, teach]);

  return {
    issueCount,
    checking,
    checkNow,
    reveal,
    ignore,
    teach,
    teaching,
    closeTeaching,
  };
}
