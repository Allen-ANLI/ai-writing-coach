"use client";

import { useState } from "react";

import { Dialog } from "@/components/dialog";
import { ApiClientError } from "@/lib/api-client";
import type { EssayData, WritingType } from "@/types/api";

const inputClass =
  "w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:border-zinc-500 dark:focus:ring-zinc-800";

const primaryButtonClass =
  "rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300";

const secondaryButtonClass =
  "rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900";

export const WRITING_TYPE_LABELS: Record<WritingType, string> = {
  free_writing: "自由写作",
  ielts_task1: "IELTS Task 1",
  ielts_task2: "IELTS Task 2",
  other: "其他",
};

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiClientError) {
    return caught.message;
  }
  return "无法连接服务器，请稍后重试。";
}

export function CreateEssayDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (payload: {
    title: string | null;
    writing_type: WritingType;
    question_prompt: string | null;
  }) => Promise<unknown>;
}) {
  const [title, setTitle] = useState("");
  const [writingType, setWritingType] = useState<WritingType>("free_writing");
  const [questionPrompt, setQuestionPrompt] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await onCreate({
        title: title.trim() === "" ? null : title.trim(),
        writing_type: writingType,
        question_prompt: questionPrompt.trim() === "" ? null : questionPrompt.trim(),
      });
    } catch (caught) {
      setError(errorMessage(caught));
      setPending(false);
    }
  }

  return (
    <Dialog title="新建作文" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4" data-testid="create-dialog">
        <div>
          <label htmlFor="essay-title" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            标题 <span className="font-normal text-zinc-400">（可选）</span>
          </label>
          <input
            id="essay-title"
            data-testid="essay-title-input"
            type="text"
            maxLength={255}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className={inputClass}
            autoFocus
          />
        </div>
        <div>
          <label htmlFor="essay-type" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            写作类型
          </label>
          <select
            id="essay-type"
            data-testid="essay-type-select"
            value={writingType}
            onChange={(event) => setWritingType(event.target.value as WritingType)}
            className={inputClass}
          >
            {(Object.keys(WRITING_TYPE_LABELS) as WritingType[]).map((value) => (
              <option key={value} value={value}>
                {WRITING_TYPE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="essay-question" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            题目 <span className="font-normal text-zinc-400">（可选 — 独立显示，不混入正文）</span>
          </label>
          <textarea
            id="essay-question"
            data-testid="essay-question-input"
            rows={3}
            maxLength={5000}
            value={questionPrompt}
            onChange={(event) => setQuestionPrompt(event.target.value)}
            className={inputClass}
            placeholder="在此粘贴作文题目或写作要求…"
          />
        </div>
        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            取消
          </button>
          <button type="submit" disabled={pending} className={primaryButtonClass} data-testid="submit-create">
            {pending ? "创建中…" : "创建作文"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function RenameEssayDialog({
  essay,
  onClose,
  onRename,
}: {
  essay: EssayData;
  onClose: () => void;
  onRename: (title: string | null) => Promise<unknown>;
}) {
  const [title, setTitle] = useState(essay.title ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await onRename(title.trim() === "" ? null : title.trim());
    } catch (caught) {
      setError(errorMessage(caught));
      setPending(false);
    }
  }

  return (
    <Dialog title="重命名作文" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4" data-testid="rename-dialog">
        <div>
          <label htmlFor="rename-title" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            标题
          </label>
          <input
            id="rename-title"
            data-testid="essay-title-input"
            type="text"
            maxLength={255}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className={inputClass}
            autoFocus
          />
        </div>
        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            取消
          </button>
          <button type="submit" disabled={pending} className={primaryButtonClass} data-testid="save-rename">
            {pending ? "保存中…" : "保存"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function DeleteEssayDialog({
  essay,
  onClose,
  onConfirm,
}: {
  essay: EssayData;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setPending(true);
    setError(null);
    try {
      await onConfirm();
    } catch (caught) {
      setError(errorMessage(caught));
      setPending(false);
    }
  }

  return (
    <Dialog title="删除作文" onClose={onClose}>
      <div className="space-y-4" data-testid="delete-dialog">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          确定删除 <span className="font-medium text-zinc-900 dark:text-zinc-100">{essay.title ?? "未命名作文"}</span>？
          删除后将从列表中移除。
        </p>
        {error && (
          <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondaryButtonClass} data-testid="cancel-delete">
            取消
          </button>
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={pending}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500 disabled:opacity-50"
            data-testid="confirm-delete"
          >
            {pending ? "删除中…" : "删除"}
          </button>
        </div>
      </div>
    </Dialog>
  );
}
