"use client";

/**
 * Writing editor (confirmed layout): wide central canvas, collapsible left
 * outline expanded by default, no permanent right AI panel. Autosave with
 * optimistic concurrency, word count, undo/redo, checkpoints and version
 * restore. Grammar/AI feedback arrives inline in later slices.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useQuery } from "@tanstack/react-query";

import { WRITING_TYPE_LABELS } from "@/features/essays/essay-dialogs";
import { ExpressionAssist } from "@/features/editor/expression-assist";
import { createGrammarExtension } from "@/features/editor/grammar/grammar-extension";
import { GrammarHoverCard } from "@/features/editor/grammar/grammar-hover-card";
import { TeachingCard } from "@/features/editor/grammar/teaching-card";
import { useGrammar } from "@/features/editor/grammar/use-grammar";
import { OutlinePanel } from "@/features/editor/outline-panel";
import { SessionControls } from "@/features/editor/session-controls";
import { useAutosave, type AutosaveApi, type SaveStatus } from "@/features/editor/use-autosave";
import { VersionHistory } from "@/features/editor/version-history";
import { BLOCK_SEPARATOR, countWords } from "@/lib/document-text";
import { getEssay } from "@/services/essays";
import { getWorkingDocument } from "@/services/documents";
import { listSessions } from "@/services/sessions";
import type { TipTapDocument } from "@/types/api";

const SAVE_STATUS_LABELS: Record<SaveStatus, string> = {
  saved: "Saved",
  dirty: "Unsaved changes",
  saving: "Saving…",
  conflict: "Save conflict",
  error: "Save failed",
};

export function WritingEditor({ essayId }: { essayId: string }) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [mobileOutlineOpen, setMobileOutlineOpen] = useState(false);
  const [, setTick] = useState(0);

  const essayQuery = useQuery({
    queryKey: ["essay", essayId],
    queryFn: async () => (await getEssay(essayId)).data,
  });
  const documentQuery = useQuery({
    queryKey: ["working-document", essayId],
    queryFn: async () => (await getWorkingDocument(essayId)).data,
  });
  const sessionsQuery = useQuery({
    queryKey: ["sessions", essayId],
    queryFn: async () => (await listSessions(essayId)).data.items,
  });
  const activeSession =
    sessionsQuery.data?.find((session) => session.status === "active") ?? null;

  const suppressUpdateRef = useRef(false);
  const initializedRef = useRef(false);
  const composingChangedRef = useRef(false);
  const editorRef = useRef<Editor | null>(null);
  const autosaveRef = useRef<AutosaveApi | null>(null);

  const grammarExtension = useMemo(() => createGrammarExtension(), []);

  const applyContent = useCallback((content: TipTapDocument) => {
    const currentEditor = editorRef.current;
    if (!currentEditor) {
      return;
    }
    suppressUpdateRef.current = true;
    currentEditor.commands.setContent(content);
    queueMicrotask(() => {
      suppressUpdateRef.current = false;
    });
  }, []);

  const editor = useEditor({
    extensions: [StarterKit, grammarExtension],
    content: { type: "doc", content: [] },
    immediatelyRender: false,
    editorProps: {
      attributes: {
        "aria-label": "Essay text",
        "data-testid": "editor-content",
      },
    },
    onUpdate: ({ editor: updatedEditor, transaction }) => {
      if (!transaction.docChanged) {
        return;
      }
      if (updatedEditor.view.composing) {
        composingChangedRef.current = true;
        return;
      }
      if (suppressUpdateRef.current) {
        return;
      }
      autosaveRef.current?.markDirty();
      setTick((value) => value + 1);
    },
  });

  useEffect(() => {
    editorRef.current = editor;
  }, [editor]);

  const autosave = useAutosave({ essayId, editor, applyContent });

  useEffect(() => {
    autosaveRef.current = autosave;
  }, [autosave]);

  const grammar = useGrammar({ essayId, editor, session: activeSession, autosave, applyContent });

  // Initialize once per essay when both the editor and the document are ready.
  useEffect(() => {
    if (!editor || !documentQuery.data || initializedRef.current) {
      return;
    }
    initializedRef.current = true;
    applyContent(documentQuery.data.content_json);
    autosave.initialize(documentQuery.data);
    setTick((value) => value + 1);
  }, [editor, documentQuery.data, applyContent, autosave]);

  // IME composition: save after composition ends, never mid-composition.
  useEffect(() => {
    if (!editor) {
      return;
    }
    const dom = editor.view.dom;
    const onCompositionEnd = () => {
      if (composingChangedRef.current) {
        composingChangedRef.current = false;
        autosaveRef.current?.markDirty();
        setTick((value) => value + 1);
      }
    };
    dom.addEventListener("compositionend", onCompositionEnd);
    return () => dom.removeEventListener("compositionend", onCompositionEnd);
  }, [editor]);

  // Ctrl/Cmd+S saves immediately.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        autosaveRef.current?.saveNow();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleRestored = useCallback(
    (content: TipTapDocument, revision: number) => {
      applyContent(content);
      autosave.setServerRevision(revision);
      setHistoryOpen(false);
      setTick((value) => value + 1);
    },
    [applyContent, autosave],
  );

  // A fresh editor's selection sits at doc level (position 0), where block
  // commands are no-ops; place the caret inside the document in that case.
  const ensureFocus = useCallback(() => {
    if (!editor) {
      return;
    }
    if (!editor.state.selection.$from.parent.isTextblock) {
      editor.commands.focus("end");
    } else {
      editor.commands.focus();
    }
  }, [editor]);

  if (essayQuery.isPending || documentQuery.isPending) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p role="status" className="text-sm text-zinc-500 dark:text-zinc-400">
          Loading editor…
        </p>
      </main>
    );
  }

  if (essayQuery.isError || documentQuery.isError || !essayQuery.data) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12">
        <Link href="/dashboard" className="text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400">
          ← Back to essays
        </Link>
        <p role="alert" data-testid="essay-detail-error" className="mt-6 text-sm text-red-600 dark:text-red-400">
          This essay could not be loaded. It may have been deleted.
        </p>
      </main>
    );
  }

  const essay = essayQuery.data;
  const plainText = editor?.getText({ blockSeparator: BLOCK_SEPARATOR }) ?? "";
  const wordCount = countWords(plainText);
  const canUndo = editor?.can().undo() ?? false;
  const canRedo = editor?.can().redo() ?? false;

  const toolbarButton =
    "rounded px-2 py-1 text-sm text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:text-zinc-300 dark:hover:bg-zinc-800";
  const toolbarActive = "bg-zinc-200 dark:bg-zinc-700";

  return (
    <main className="flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b border-zinc-200 px-4 py-2 dark:border-zinc-800">
        <Link
          href="/dashboard"
          className="text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          ← Back to essays
        </Link>
        <button
          type="button"
          aria-label="Toggle outline"
          data-testid="toggle-outline"
          onClick={() => setMobileOutlineOpen((open) => !open)}
          className={`${toolbarButton} lg:hidden`}
        >
          Outline
        </button>
        <h1
          data-testid="essay-detail-title"
          className="min-w-0 flex-1 truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100"
        >
          {essay.title ?? "Untitled"}
        </h1>
        <button
          type="button"
          data-testid="save-now"
          onClick={() => autosave.saveNow()}
          disabled={autosave.status === "conflict"}
          className={toolbarButton}
        >
          Save now
        </button>
        <button
          type="button"
          data-testid="open-history"
          onClick={() => setHistoryOpen(true)}
          className={toolbarButton}
        >
          History
        </button>
      </header>

      <SessionControls essayId={essayId} />

      {autosave.status === "conflict" && (
        <div
          role="alert"
          data-testid="conflict-banner"
          className="flex flex-wrap items-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          <span className="flex-1">{autosave.errorMessage}</span>
          <button
            type="button"
            data-testid="copy-my-text"
            onClick={() => void navigator.clipboard.writeText(plainText)}
            className="rounded-md border border-amber-300 px-2 py-1 text-xs font-medium hover:bg-amber-100 dark:border-amber-800 dark:hover:bg-amber-900"
          >
            Copy my text
          </button>
          <button
            type="button"
            data-testid="load-latest"
            onClick={() => void autosave.loadLatest()}
            className="rounded-md bg-amber-600 px-2 py-1 text-xs font-medium text-white hover:bg-amber-700"
          >
            Load latest version
          </button>
        </div>
      )}

      {autosave.status === "error" && (
        <div
          role="alert"
          data-testid="save-error-banner"
          className="flex items-center gap-3 border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
        >
          <span className="flex-1">{autosave.errorMessage}</span>
          <button
            type="button"
            data-testid="retry-save"
            onClick={() => autosave.saveNow()}
            className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-64 shrink-0 border-r border-zinc-200 dark:border-zinc-800 lg:block">
          <OutlinePanel
            editor={editor}
            essayTitle={essay.title ?? "Untitled"}
            writingTypeLabel={WRITING_TYPE_LABELS[essay.writing_type]}
          />
        </aside>

        {mobileOutlineOpen && (
          <div className="fixed inset-0 z-40 flex lg:hidden" onClick={() => setMobileOutlineOpen(false)}>
            <div className="h-full w-72 max-w-[85%] bg-white shadow-xl dark:bg-zinc-950" onClick={(event) => event.stopPropagation()}>
              <OutlinePanel
                editor={editor}
                essayTitle={essay.title ?? "Untitled"}
                writingTypeLabel={WRITING_TYPE_LABELS[essay.writing_type]}
              />
            </div>
            <div className="flex-1 bg-black/30" />
          </div>
        )}

        <div className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-6 py-6">
            {essay.question_prompt && (
              <section
                aria-label="Essay question"
                data-testid="question-section"
                className="mb-5 rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                  Question
                </h2>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
                  {essay.question_prompt}
                </p>
              </section>
            )}
            <div className="mb-4 flex flex-wrap items-center gap-1 border-b border-zinc-100 pb-2 dark:border-zinc-900">
              <button type="button" aria-label="Undo" data-testid="undo" disabled={!canUndo} onClick={() => { ensureFocus(); editor?.chain().undo().run(); }} className={toolbarButton}>
                Undo
              </button>
              <button type="button" aria-label="Redo" data-testid="redo" disabled={!canRedo} onClick={() => { ensureFocus(); editor?.chain().redo().run(); }} className={toolbarButton}>
                Redo
              </button>
              <span className="mx-1 h-4 w-px bg-zinc-200 dark:bg-zinc-700" />
              <button type="button" aria-label="Bold" aria-pressed={editor?.isActive("bold") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleBold().run(); }} className={`${toolbarButton} ${editor?.isActive("bold") ? toolbarActive : ""}`}>
                <strong>B</strong>
              </button>
              <button type="button" aria-label="Italic" aria-pressed={editor?.isActive("italic") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleItalic().run(); }} className={`${toolbarButton} ${editor?.isActive("italic") ? toolbarActive : ""}`}>
                <em>I</em>
              </button>
              <button type="button" aria-label="Heading 1" aria-pressed={editor?.isActive("heading", { level: 1 }) ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleHeading({ level: 1 }).run(); }} className={`${toolbarButton} ${editor?.isActive("heading", { level: 1 }) ? toolbarActive : ""}`}>
                H1
              </button>
              <button type="button" aria-label="Heading 2" aria-pressed={editor?.isActive("heading", { level: 2 }) ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleHeading({ level: 2 }).run(); }} className={`${toolbarButton} ${editor?.isActive("heading", { level: 2 }) ? toolbarActive : ""}`}>
                H2
              </button>
              <button type="button" aria-label="Bullet list" aria-pressed={editor?.isActive("bulletList") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleBulletList().run(); }} className={`${toolbarButton} ${editor?.isActive("bulletList") ? toolbarActive : ""}`}>
                • List
              </button>
              <button type="button" aria-label="Quote" aria-pressed={editor?.isActive("blockquote") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleBlockquote().run(); }} className={`${toolbarButton} ${editor?.isActive("blockquote") ? toolbarActive : ""}`}>
                Quote
              </button>
            </div>
            <EditorContent editor={editor} className="awc-editor" />
          </div>
        </div>
      </div>

      <footer className="flex items-center gap-4 border-t border-zinc-200 px-4 py-1.5 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        <span data-testid="word-count">{wordCount} words</span>
        {activeSession?.enabled_features.realtime_grammar && (
          <span data-testid="issue-count">{grammar.issueCount} issues</span>
        )}
        <span
          data-testid="save-status"
          className={
            autosave.status === "conflict" || autosave.status === "error"
              ? "font-medium text-red-600 dark:text-red-400"
              : autosave.status === "saved"
                ? "text-emerald-600 dark:text-emerald-400"
                : ""
          }
        >
          {SAVE_STATUS_LABELS[autosave.status]}
          {autosave.status === "saved" && autosave.lastSavedAt
            ? ` · ${new Date(autosave.lastSavedAt).toLocaleTimeString()}`
            : ""}
        </span>
        <span className="ml-auto hidden sm:inline">
          rev {autosave.serverRevision} · Ctrl+S saves · autosave on
        </span>
      </footer>

      {historyOpen && (
        <VersionHistory
          essayId={essayId}
          serverRevision={autosave.serverRevision}
          saveStatus={autosave.status}
          onClose={() => setHistoryOpen(false)}
          onRestored={handleRestored}
        />
      )}

      {grammar.hoverCard && (
        <GrammarHoverCard
          state={grammar.hoverCard}
          onRevealAnswer={grammar.revealAnswer}
          onTeach={grammar.teachFromCard}
          onMouseEnter={grammar.onCardMouseEnter}
          onMouseLeave={grammar.onCardMouseLeave}
        />
      )}

      <ExpressionAssist
        essayId={essayId}
        editor={editor}
        session={activeSession}
        autosave={autosave}
        applyContent={applyContent}
      />

      {grammar.teaching && (
        <TeachingCard teaching={grammar.teaching} onClose={grammar.closeTeaching} />
      )}
    </main>
  );
}
