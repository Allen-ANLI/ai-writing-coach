"use client";

/**
 * 写作编辑器（ADR-024 布局）：中央宽画布 + 左侧构思助手对话面板。
 * 打开时若无活动会话自动创建辅助学习会话（语法检查即时可用）；
 * 已确认大纲驱动光标处的灰色中文指引；右上不再有 Plan 按钮，
 * 编辑器内不再维护文档大纲树。自动保存、字数、撤销/重做、历史版本保留。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applyServerContent } from "@/features/editor/apply-content";
import { EvaluationDialog } from "@/features/editor/evaluation-dialog";
import { ExpressionAssist } from "@/features/editor/expression-assist";
import { createExpressionExtension } from "@/features/editor/expression-extension";
import {
  advanceGhostHint,
  createGhostHintExtension,
  getGhostIndex,
  setGhostConfig,
  setGhostIndex,
} from "@/features/editor/ghost-hint-extension";
import { createGrammarExtension } from "@/features/editor/grammar/grammar-extension";
import { GrammarHoverCard } from "@/features/editor/grammar/grammar-hover-card";
import { useGrammar } from "@/features/editor/grammar/use-grammar";
import { PlannerChatPanel } from "@/features/editor/planner-chat-panel";
import { PolishCard } from "@/features/editor/polish-card";
import { RecordsDialog } from "@/features/editor/records-dialog";
import { SessionControls } from "@/features/editor/session-controls";
import { usePolish } from "@/features/editor/use-polish";
import { useAutosave, type AutosaveApi, type SaveStatus } from "@/features/editor/use-autosave";
import { VersionHistory } from "@/features/editor/version-history";
import { BLOCK_SEPARATOR, countWords, splitSentences } from "@/lib/document-text";
import { getEssay } from "@/services/essays";
import { getWorkingDocument } from "@/services/documents";
import { getOutline, listOutlines } from "@/services/outlines";
import { judgeGhostProgress } from "@/services/planner";
import { getPreferences, patchPreferences } from "@/services/preferences";
import { createSession, listSessions } from "@/services/sessions";
import type { TipTapDocument } from "@/types/api";

const SAVE_STATUS_LABELS: Record<SaveStatus, string> = {
  saved: "已保存",
  dirty: "有未保存修改",
  saving: "保存中…",
  conflict: "保存冲突",
  error: "保存失败",
};

export function WritingEditor({ essayId }: { essayId: string }) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [evaluationOpen, setEvaluationOpen] = useState(false);
  const [recordsOpen, setRecordsOpen] = useState(false);
  const [mobileChatOpen, setMobileChatOpen] = useState(false);
  const [, setTick] = useState(0);
  const queryClient = useQueryClient();

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

  // 打开编辑器即自动进入辅助学习会话，语法检查无需手动启动（ADR-024）。
  // 仅在"从未有过会话"或"最近一次会话已提交（继续写作）"时自动创建；
  // 用户显式取消后不自动重建，独立写作/模拟考试由会话栏显式切换。
  const autoSessionAttemptedRef = useRef(false);
  useEffect(() => {
    if (!sessionsQuery.isSuccess || activeSession || autoSessionAttemptedRef.current) {
      return;
    }
    const sessions = sessionsQuery.data ?? [];
    const latest = sessions[0];
    if (latest && latest.status !== "submitted") {
      return;
    }
    autoSessionAttemptedRef.current = true;
    void createSession(essayId, {
      mode: "assisted",
      activity_type: "free_writing",
      exam_config: null,
    })
      .then(() => {
        void queryClient.invalidateQueries({ queryKey: ["sessions", essayId] });
      })
      .catch(() => {
        autoSessionAttemptedRef.current = false;
      });
  }, [sessionsQuery.isSuccess, sessionsQuery.data, activeSession, essayId, queryClient]);

  const outlinesQuery = useQuery({
    queryKey: ["outlines", essayId],
    queryFn: async () => (await listOutlines(essayId)).data.items,
  });
  const confirmedPlan = outlinesQuery.data?.find((item) => item.status === "confirmed") ?? null;
  const planQuery = useQuery({
    queryKey: ["outline", confirmedPlan?.id],
    queryFn: async () => (await getOutline(confirmedPlan?.id as string)).data,
    enabled: confirmedPlan !== null,
  });
  // ADR-025: 大纲展平为有序句子指引（无范文时的回退）。
  const flatIdeas = useMemo<string[]>(() => {
    const nodes = planQuery.data?.nodes ?? [];
    const byParent = (parentId: string | null) =>
      nodes
        .filter((node) => node.parent_id === parentId)
        .sort((a, b) => a.sort_order - b.sort_order);
    const ideas: string[] = [];
    for (const section of byParent(null)) {
      for (const paragraph of byParent(section.id)) {
        ideas.push(...byParent(paragraph.id).map((idea) => idea.title));
      }
    }
    return ideas;
  }, [planQuery.data]);
  // ADR-029: 有范文时，幽灵指引 = 范文的逐句序列；否则回退大纲指引。
  const modelEssay = planQuery.data?.model_essay ?? null;
  const ghostHints = useMemo<string[]>(() => {
    if (modelEssay && modelEssay.trim() !== "") {
      return splitSentences(modelEssay)
        .map((span) => span.text.trim())
        .filter((text) => text !== "");
    }
    return flatIdeas;
  }, [modelEssay, flatIdeas]);

  const preferencesQuery = useQuery({
    queryKey: ["preferences"],
    queryFn: async () => (await getPreferences()).data,
  });
  const ghostEnabled = preferencesQuery.data?.ghost_hints_enabled ?? true;
  const toggleGhost = useMutation({
    mutationFn: async (enabled: boolean) => patchPreferences({ ghost_hints_enabled: enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["preferences"] });
    },
  });
  const [ghostIndex, setGhostIndexState] = useState(0);
  const guidanceDone = ghostHints.length > 0 && ghostIndex >= ghostHints.length;

  const suppressUpdateRef = useRef(false);
  const initializedRef = useRef(false);
  const composingChangedRef = useRef(false);
  const editorRef = useRef<Editor | null>(null);
  const autosaveRef = useRef<AutosaveApi | null>(null);

  const grammarExtension = useMemo(() => createGrammarExtension(), []);
  const ghostExtension = useMemo(() => createGhostHintExtension(), []);
  const expressionExtension = useMemo(() => createExpressionExtension(), []);

  // ADR-027: minimal-diff replacement — a full setContent would collapse
  // every grammar/polish decoration position and wipe all other highlights.
  const applyContent = useCallback((content: TipTapDocument) => {
    const currentEditor = editorRef.current;
    if (!currentEditor) {
      return;
    }
    suppressUpdateRef.current = true;
    applyServerContent(currentEditor, content);
    queueMicrotask(() => {
      suppressUpdateRef.current = false;
    });
  }, []);

  const editor = useEditor({
    extensions: [StarterKit, grammarExtension, ghostExtension, expressionExtension],
    content: { type: "doc", content: [] },
    immediatelyRender: false,
    editorProps: {
      attributes: {
        "aria-label": "作文正文",
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
      maybeJudgeProgressRef.current();
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
  const polish = usePolish({ essayId, editor, session: activeSession, autosave, applyContent });

  // ADR-025/029: 句点完成 → 大意匹配当前范文句 → 达成则推进；
  // 未达成时追赶判断下一句（写超前了也不卡死）。
  const ghostEnabledRef = useRef(ghostEnabled);
  const ghostHintsRef = useRef(ghostHints);
  const processedSentencesRef = useRef(0);
  const judgingRef = useRef(false);
  useEffect(() => {
    ghostEnabledRef.current = ghostEnabled;
    ghostHintsRef.current = ghostHints;
  });

  const maybeJudgeProgress = useCallback(() => {
    const current = editorRef.current;
    const ideas = ghostHintsRef.current;
    if (!current || !ghostEnabledRef.current || judgingRef.current) {
      return;
    }
    const index = getGhostIndex(current.view);
    if (index >= ideas.length) {
      return;
    }
    const plain = current.getText({ blockSeparator: BLOCK_SEPARATOR });
    const completed = splitSentences(plain).filter((s) => s.complete);
    if (completed.length <= processedSentencesRef.current) {
      return;
    }
    const sentence = completed[completed.length - 1].text.trim();
    if (!sentence) {
      return;
    }
    judgingRef.current = true;
    void judgeGhostProgress(essayId, {
      sentence,
      idea_index: index,
      idea: ideas[index],
    })
      .then((response) => {
        processedSentencesRef.current = completed.length;
        const latest = editorRef.current;
        if (!latest || getGhostIndex(latest.view) !== index) {
          return;
        }
        if (response.data.fulfilled) {
          advanceGhostHint(latest.view);
          setGhostIndexState(index + 1);
          return;
        }
        // ADR-029 追赶：当前句未匹配时，可能已写到下一句范文的内容；
        // 再判一次下一句（服务端缓存防重复花费），匹配则跳到对应位置。
        const nextIdea = ideas[index + 1];
        if (!nextIdea) {
          return;
        }
        void judgeGhostProgress(essayId, {
          sentence,
          idea_index: index + 1,
          idea: nextIdea,
        })
          .then((next) => {
            const now = editorRef.current;
            if (next.data.fulfilled && now && getGhostIndex(now.view) === index) {
              setGhostIndex(now.view, index + 2);
              setGhostIndexState(index + 2);
            }
          })
          .catch(() => undefined);
      })
      .catch(() => {
        // Provider/network failure: never block the writer; keep the hint.
        processedSentencesRef.current = completed.length;
      })
      .finally(() => {
        judgingRef.current = false;
      });
  }, [essayId]);
  const maybeJudgeProgressRef = useRef(maybeJudgeProgress);
  useEffect(() => {
    maybeJudgeProgressRef.current = maybeJudgeProgress;
  }, [maybeJudgeProgress]);

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

  // 已确认大纲 → 灰色指引（范文逐句；无范文回退大纲指引）。
  // ADR-026：大纲更新后按已完成句数续接，不再从第一句重新开始。
  useEffect(() => {
    if (!editor) {
      return;
    }
    setGhostConfig(editor.view, ghostHints, ghostEnabled);
    let nextIndex = getGhostIndex(editor.view);
    const plain = editor.getText({ blockSeparator: BLOCK_SEPARATOR });
    const completedCount = splitSentences(plain).filter((s) => s.complete).length;
    if (ghostHints.length > 0 && completedCount > nextIndex) {
      nextIndex = Math.min(completedCount, ghostHints.length);
      setGhostIndex(editor.view, nextIndex);
    }
    processedSentencesRef.current = completedCount;
    queueMicrotask(() => setGhostIndexState(nextIndex));
  }, [editor, ghostHints, ghostEnabled]);

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

  const handleRewriteAccepted = useCallback(
    (content: TipTapDocument, revision: number) => {
      applyContent(content);
      autosave.setServerRevision(revision);
      setEvaluationOpen(false);
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
          编辑器加载中…
        </p>
      </main>
    );
  }

  if (essayQuery.isError || documentQuery.isError || !essayQuery.data) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12">
        <Link href="/dashboard" className="text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400">
          ← 返回作文列表
        </Link>
        <p role="alert" data-testid="essay-detail-error" className="mt-6 text-sm text-red-600 dark:text-red-400">
          无法加载这篇作文，它可能已被删除。
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
          ← 返回作文列表
        </Link>
        <button
          type="button"
          aria-label="打开构思助手"
          data-testid="toggle-planner-chat"
          onClick={() => setMobileChatOpen((open) => !open)}
          className={`${toolbarButton} lg:hidden`}
        >
          构思助手
        </button>
        <h1
          data-testid="essay-detail-title"
          className="min-w-0 flex-1 truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100"
        >
          {essay.title ?? "未命名作文"}
        </h1>
        <button
          type="button"
          data-testid="save-now"
          onClick={() => autosave.saveNow()}
          disabled={autosave.status === "conflict"}
          className={toolbarButton}
        >
          立即保存
        </button>
        <button
          type="button"
          data-testid="open-history"
          onClick={() => setHistoryOpen(true)}
          className={toolbarButton}
        >
          历史版本
        </button>
        <button
          type="button"
          data-testid="open-evaluation"
          onClick={() => setEvaluationOpen(true)}
          className={toolbarButton}
        >
          评分
        </button>
        <button
          type="button"
          data-testid="open-records"
          onClick={() => setRecordsOpen(true)}
          className={toolbarButton}
        >
          错误与优化记录
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
            复制我的文本
          </button>
          <button
            type="button"
            data-testid="load-latest"
            onClick={() => void autosave.loadLatest()}
            className="rounded-md bg-amber-600 px-2 py-1 text-xs font-medium text-white hover:bg-amber-700"
          >
            加载最新版本
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
            重试
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-72 shrink-0 border-r border-zinc-200 dark:border-zinc-800 lg:block">
          <PlannerChatPanel
            essayId={essayId}
            ghostEnabled={ghostEnabled}
            guidanceDone={guidanceDone}
            onToggleGhost={(enabled) => toggleGhost.mutate(enabled)}
          />
        </aside>

        {mobileChatOpen && (
          <div className="fixed inset-0 z-40 flex lg:hidden" onClick={() => setMobileChatOpen(false)}>
            <div className="h-full w-80 max-w-[85%] bg-white shadow-xl dark:bg-zinc-950" onClick={(event) => event.stopPropagation()}>
              <PlannerChatPanel
                essayId={essayId}
                ghostEnabled={ghostEnabled}
                guidanceDone={guidanceDone}
                onToggleGhost={(enabled) => toggleGhost.mutate(enabled)}
              />
            </div>
            <div className="flex-1 bg-black/30" />
          </div>
        )}

        <div className="awc-scroll min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-6 py-6">
            {essay.question_prompt && (
              <section
                aria-label="作文题目"
                data-testid="question-section"
                className="mb-5 rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                  题目
                </h2>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
                  {essay.question_prompt}
                </p>
              </section>
            )}
            <div className="mb-4 flex flex-wrap items-center gap-1 border-b border-zinc-100 pb-2 dark:border-zinc-900">
              <button type="button" aria-label="撤销" data-testid="undo" disabled={!canUndo} onClick={() => { ensureFocus(); editor?.chain().undo().run(); }} className={toolbarButton}>
                撤销
              </button>
              <button type="button" aria-label="重做" data-testid="redo" disabled={!canRedo} onClick={() => { ensureFocus(); editor?.chain().redo().run(); }} className={toolbarButton}>
                重做
              </button>
              <span className="mx-1 h-4 w-px bg-zinc-200 dark:bg-zinc-700" />
              <button type="button" aria-label="加粗" aria-pressed={editor?.isActive("bold") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleBold().run(); }} className={`${toolbarButton} ${editor?.isActive("bold") ? toolbarActive : ""}`}>
                <strong>B</strong>
              </button>
              <button type="button" aria-label="斜体" aria-pressed={editor?.isActive("italic") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleItalic().run(); }} className={`${toolbarButton} ${editor?.isActive("italic") ? toolbarActive : ""}`}>
                <em>I</em>
              </button>
              <button type="button" aria-label="一级标题" aria-pressed={editor?.isActive("heading", { level: 1 }) ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleHeading({ level: 1 }).run(); }} className={`${toolbarButton} ${editor?.isActive("heading", { level: 1 }) ? toolbarActive : ""}`}>
                H1
              </button>
              <button type="button" aria-label="二级标题" aria-pressed={editor?.isActive("heading", { level: 2 }) ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleHeading({ level: 2 }).run(); }} className={`${toolbarButton} ${editor?.isActive("heading", { level: 2 }) ? toolbarActive : ""}`}>
                H2
              </button>
              <button type="button" aria-label="无序列表" aria-pressed={editor?.isActive("bulletList") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleBulletList().run(); }} className={`${toolbarButton} ${editor?.isActive("bulletList") ? toolbarActive : ""}`}>
                • 列表
              </button>
              <button type="button" aria-label="引用" aria-pressed={editor?.isActive("blockquote") ?? false} onClick={() => { ensureFocus(); editor?.chain().toggleBlockquote().run(); }} className={`${toolbarButton} ${editor?.isActive("blockquote") ? toolbarActive : ""}`}>
                引用
              </button>
            </div>
            <EditorContent editor={editor} className="awc-editor" />
          </div>
        </div>
      </div>

      <footer className="flex items-center gap-4 border-t border-zinc-200 px-4 py-1.5 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        <span data-testid="word-count">{wordCount} 词</span>
        {activeSession?.enabled_features.realtime_grammar && (
          <span data-testid="issue-count">{grammar.issueCount} 处问题</span>
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
          修订 {autosave.serverRevision} · Ctrl+S 保存 · 自动保存已开启
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

      {evaluationOpen && essayQuery.data && (
        <EvaluationDialog
          essayId={essayId}
          writingType={essayQuery.data.writing_type}
          serverRevision={autosave.serverRevision}
          saveStatus={autosave.status}
          onClose={() => setEvaluationOpen(false)}
          onRewriteAccepted={handleRewriteAccepted}
        />
      )}

      {grammar.hoverCard && (
        <GrammarHoverCard
          state={grammar.hoverCard}
          onSelectSuggestion={grammar.selectSuggestion}
          onAccept={grammar.acceptCorrection}
          onIgnore={grammar.ignoreFromCard}
          onRequestTeaching={grammar.requestTeaching}
          onMouseEnter={grammar.onCardMouseEnter}
          onMouseLeave={grammar.onCardMouseLeave}
        />
      )}

      {polish.card && (
        <PolishCard
          state={polish.card}
          onSelect={polish.selectItem}
          onAccept={polish.acceptSelected}
          onNextPage={polish.nextPage}
          onPrevPage={polish.prevPage}
          onAddToKb={polish.addSelectedToKb}
          onMouseEnter={polish.onCardMouseEnter}
          onMouseLeave={polish.onCardMouseLeave}
        />
      )}

      {recordsOpen && (
        <RecordsDialog essayId={essayId} onClose={() => setRecordsOpen(false)} />
      )}

      <ExpressionAssist
        essayId={essayId}
        editor={editor}
        session={activeSession}
        autosave={autosave}
        applyContent={applyContent}
      />
    </main>
  );
}
