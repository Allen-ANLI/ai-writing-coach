"use client";

/**
 * Debounced autosave with optimistic concurrency (API Spec §4.2).
 *
 * - Edits mark the document dirty and schedule a save after DEBOUNCE_MS.
 * - Saves carry base_revision; a 409 WORKING_DOCUMENT_CONFLICT switches to a
 *   conflict state that never overwrites local edits or the server silently.
 * - IME composition is respected: the caller skips markDirty while composing
 *   and calls it again on compositionend.
 * - Programmatic content replacement (initial load, restore, conflict reload)
 *   must go through applyContent so it does not trigger an autosave loop.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";

import { ApiClientError } from "@/lib/api-client";
import { BLOCK_SEPARATOR, countWords } from "@/lib/document-text";
import { getWorkingDocument, saveWorkingDocument } from "@/services/documents";
import type { TipTapDocument, WorkingDocumentData } from "@/types/api";

export type SaveStatus = "saved" | "dirty" | "saving" | "conflict" | "error";

const DEBOUNCE_MS = 1500;

export interface AutosaveApi {
  status: SaveStatus;
  serverRevision: number;
  clientRevision: number;
  lastSavedAt: string | null;
  errorMessage: string | null;
  initialize: (document: WorkingDocumentData) => void;
  markDirty: () => void;
  saveNow: () => void;
  loadLatest: () => Promise<void>;
  setServerRevision: (revision: number) => void;
}

export function useAutosave({
  essayId,
  editor,
  applyContent,
}: {
  essayId: string;
  editor: Editor | null;
  applyContent: (content: TipTapDocument) => void;
}): AutosaveApi {
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [serverRevision, setServerRevisionState] = useState(1);
  const [clientRevision, setClientRevision] = useState(0);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const editorRef = useRef<Editor | null>(editor);
  const applyContentRef = useRef(applyContent);
  useEffect(() => {
    editorRef.current = editor;
  }, [editor]);
  useEffect(() => {
    applyContentRef.current = applyContent;
  }, [applyContent]);

  const serverRevisionRef = useRef(1);
  const clientRevisionRef = useRef(0);
  const dirtyRef = useRef(false);
  const savingRef = useRef(false);
  const initializedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const doSaveRef = useRef<(() => Promise<void>) | null>(null);

  const clearTimer = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const doSave = useCallback(async () => {
    const currentEditor = editorRef.current;
    if (!currentEditor || savingRef.current || !initializedRef.current) {
      return;
    }
    if (!dirtyRef.current) {
      return;
    }
    clearTimer();
    savingRef.current = true;
    dirtyRef.current = false;
    setStatus("saving");
    setErrorMessage(null);

    const contentJson = currentEditor.getJSON() as TipTapDocument;
    const plainText = currentEditor.getText({ blockSeparator: BLOCK_SEPARATOR });
    const baseRevision = serverRevisionRef.current;
    const sentClientRevision = clientRevisionRef.current;

    try {
      const response = await saveWorkingDocument(essayId, {
        base_revision: baseRevision,
        client_revision: sentClientRevision,
        content_json: contentJson,
        plain_text: plainText,
        word_count: countWords(plainText),
      });
      serverRevisionRef.current = response.data.server_revision;
      setServerRevisionState(response.data.server_revision);
      setLastSavedAt(response.data.saved_at);
      if (dirtyRef.current) {
        // Edited while the save was in flight: save again shortly.
        setStatus("dirty");
        timerRef.current = setTimeout(() => void doSaveRef.current?.(), DEBOUNCE_MS);
      } else {
        setStatus("saved");
      }
    } catch (error) {
      dirtyRef.current = true;
      if (error instanceof ApiClientError && error.status === 409) {
        setStatus("conflict");
        setErrorMessage(
          "这篇作文在其他地方被修改了。你的编辑仍保留在这里，但保存已暂停。",
        );
      } else {
        setStatus("error");
        setErrorMessage(
          error instanceof ApiClientError ? error.message : "自动保存失败，请检查网络连接。",
        );
      }
    } finally {
      savingRef.current = false;
    }
  }, [essayId]);

  useEffect(() => {
    doSaveRef.current = doSave;
  }, [doSave]);

  const scheduleSave = useCallback(() => {
    clearTimer();
    timerRef.current = setTimeout(() => void doSave(), DEBOUNCE_MS);
  }, [doSave]);

  const initialize = useCallback((document: WorkingDocumentData) => {
    clearTimer();
    initializedRef.current = true;
    dirtyRef.current = false;
    serverRevisionRef.current = document.server_revision;
    clientRevisionRef.current = 0;
    setServerRevisionState(document.server_revision);
    setClientRevision(0);
    setLastSavedAt(document.last_saved_at);
    setStatus("saved");
    setErrorMessage(null);
  }, []);

  const markDirty = useCallback(() => {
    if (!initializedRef.current) {
      return;
    }
    clientRevisionRef.current += 1;
    setClientRevision(clientRevisionRef.current);
    dirtyRef.current = true;
    if (!savingRef.current) {
      setStatus("dirty");
      scheduleSave();
    }
  }, [scheduleSave]);

  const saveNow = useCallback(() => {
    if (!initializedRef.current) {
      return;
    }
    if (status === "conflict") {
      return;
    }
    dirtyRef.current = true;
    void doSave();
  }, [doSave, status]);

  const loadLatest = useCallback(async () => {
    const response = await getWorkingDocument(essayId);
    applyContentRef.current(response.data.content_json);
    initialize(response.data);
  }, [essayId, initialize]);

  const setServerRevision = useCallback((revision: number) => {
    serverRevisionRef.current = revision;
    setServerRevisionState(revision);
  }, []);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirtyRef.current || savingRef.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  useEffect(() => clearTimer, []);

  return {
    status,
    serverRevision,
    clientRevision,
    lastSavedAt,
    errorMessage,
    initialize,
    markDirty,
    saveNow,
    loadLatest,
    setServerRevision,
  };
}
