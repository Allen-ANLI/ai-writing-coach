"use client";

/**
 * 左侧对话式构思面板（ADR-024，取代旧版大纲面板 + Plan 弹窗）：
 * 写作前与智能体对话确认文章结构；写作途中可随时再次对话调整结构。
 * 智能体提出的大纲以卡片呈现，用户点击"确认大纲"后生效（驱动灰色指引）。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { OutlineMarkdown } from "@/features/editor/outline-markdown";
import { ApiClientError } from "@/lib/api-client";
import { confirmOutline, generateModelEssay, getOutline } from "@/services/outlines";
import { listPlannerMessages, sendPlannerMessage } from "@/services/planner";
import type { OutlineNodeData } from "@/types/api";

function PlanBranch({ nodes, parentId }: { nodes: OutlineNodeData[]; parentId: string | null }) {
  const children = nodes
    .filter((node) => node.parent_id === parentId)
    .sort((a, b) => a.sort_order - b.sort_order);
  if (children.length === 0) {
    return null;
  }
  return (
    <ul className={parentId !== null ? "ml-3 border-l border-zinc-200 pl-2 dark:border-zinc-700" : ""}>
      {children.map((node) => (
        <li key={node.id} className="mt-0.5">
          <p
            className={
              node.node_type === "section"
                ? "text-xs font-semibold text-zinc-800 dark:text-zinc-200"
                : node.node_type === "paragraph"
                  ? "text-xs text-zinc-600 dark:text-zinc-300"
                  : "text-xs text-zinc-500 dark:text-zinc-400"
            }
          >
            {node.node_type === "sentence_idea" ? "· " : ""}
            {node.title}
          </p>
          <PlanBranch nodes={nodes} parentId={node.id} />
        </li>
      ))}
    </ul>
  );
}

function OutlineCard({ outlineId, essayId }: { outlineId: string; essayId: string }) {
  const queryClient = useQueryClient();
  const outlineQuery = useQuery({
    queryKey: ["outline", outlineId],
    queryFn: async () => (await getOutline(outlineId)).data,
  });
  const confirm = useMutation({
    mutationFn: async () => confirmOutline(outlineId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["outline", outlineId] });
      void queryClient.invalidateQueries({ queryKey: ["outlines", essayId] });
    },
  });
  // ADR-030: bootstrap the model essay for a confirmed outline that lacks one
  // (legacy outlines), so ghost guidance can start.
  const generateEssay = useMutation({
    mutationFn: async () => generateModelEssay(outlineId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["outline", outlineId] });
      void queryClient.invalidateQueries({ queryKey: ["outlines", essayId] });
    },
  });
  const outline = outlineQuery.data;
  if (!outline) {
    return null;
  }
  return (
    <div
      data-testid="planner-outline-card"
      className="mt-2 rounded-lg border border-zinc-200 bg-white p-2.5 dark:border-zinc-700 dark:bg-zinc-900"
    >
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold text-zinc-700 dark:text-zinc-200">
          大纲方案 v{outline.version_no}
        </h4>
        {outline.status === "confirmed" && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
            已确认
          </span>
        )}
        {outline.status === "archived" && (
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
            已归档
          </span>
        )}
      </div>
      {outline.thesis_statement && (
        <p className="mt-1 text-xs italic text-zinc-600 dark:text-zinc-300">
          {outline.thesis_statement}
        </p>
      )}
      <div className="mt-1.5">
        {outline.outline_md ? (
          <OutlineMarkdown md={outline.outline_md} />
        ) : (
          <PlanBranch nodes={outline.nodes} parentId={null} />
        )}
      </div>
      {(outline.model_essay || outline.model_essay_zh) && (
        <details className="mt-2" data-testid="model-essay-details">
          <summary className="cursor-pointer text-[11px] font-medium text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200">
            参考范文（英文 + 中文逐句对照）
          </summary>
          {outline.model_essay_zh && (
            <div className="mt-1">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                中文翻译（写作指引来源）
              </p>
              <p className="mt-0.5 whitespace-pre-wrap rounded bg-zinc-50 p-2 text-[11px] leading-relaxed text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                {outline.model_essay_zh}
              </p>
            </div>
          )}
          {outline.model_essay && (
            <div className="mt-1.5">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                英文范文
              </p>
              <p className="mt-0.5 whitespace-pre-wrap rounded bg-zinc-50 p-2 text-[11px] leading-relaxed text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                {outline.model_essay}
              </p>
            </div>
          )}
        </details>
      )}
      {outline.status === "confirmed" && !outline.model_essay_zh && (
        <div className="mt-2">
          <button
            type="button"
            data-testid="generate-model-essay"
            disabled={generateEssay.isPending}
            onClick={() => generateEssay.mutate()}
            className="rounded-md bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-700 disabled:opacity-50"
          >
            {generateEssay.isPending ? "正在生成范文…" : "生成范文指引"}
          </button>
          <p className="mt-1 text-[11px] text-zinc-400 dark:text-zinc-500">
            此大纲还没有范文，生成后即可按范文逐句提示。
          </p>
          {generateEssay.isError && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              {generateEssay.error instanceof ApiClientError
                ? generateEssay.error.message
                : "生成范文失败，请重试。"}
            </p>
          )}
        </div>
      )}
      {outline.status === "draft" && (
        <button
          type="button"
          data-testid="confirm-outline"
          disabled={confirm.isPending}
          onClick={() => confirm.mutate()}
          className="mt-2 rounded-md bg-zinc-900 px-3 py-1 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {confirm.isPending ? "确认中…" : "确认大纲"}
        </button>
      )}
      {confirm.isError && (
        <p className="mt-1 text-xs text-red-600 dark:text-red-400">
          {confirm.error instanceof ApiClientError ? confirm.error.message : "确认失败，请重试。"}
        </p>
      )}
    </div>
  );
}

export function PlannerChatPanel({
  essayId,
  ghostEnabled,
  guidanceDone,
  onToggleGhost,
}: {
  essayId: string;
  ghostEnabled: boolean;
  guidanceDone: boolean;
  onToggleGhost: (enabled: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const messagesQuery = useQuery({
    queryKey: ["planner-messages", essayId],
    queryFn: async () => (await listPlannerMessages(essayId)).data.items,
  });
  const messages = messagesQuery.data ?? [];

  const send = useMutation({
    mutationFn: async (message: string) => sendPlannerMessage(essayId, message),
    onSuccess: () => {
      setDraft("");
      setSendError(null);
      void queryClient.invalidateQueries({ queryKey: ["planner-messages", essayId] });
      void queryClient.invalidateQueries({ queryKey: ["outlines", essayId] });
    },
    onError: (error) => {
      setSendError(
        error instanceof ApiClientError ? error.message : "构思助手暂时不可用，请稍后重试。",
      );
    },
  });

  useEffect(() => {
    const node = scrollRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages.length, send.isPending]);

  const submit = useCallback(() => {
    const message = draft.trim();
    if (!message || send.isPending) {
      return;
    }
    setSendError(null);
    send.mutate(message);
  }, [draft, send]);

  return (
    <div className="flex h-full flex-col" data-testid="planner-chat-panel">
      <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">构思助手</h2>
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
          对话确认文章结构，写作途中可随时调整
        </p>
        <label className="mt-2 flex items-center justify-between gap-2 text-xs text-zinc-600 dark:text-zinc-300">
          <span>
            写作指引
            {guidanceDone && (
              <span className="ml-1 text-emerald-600 dark:text-emerald-400">（大纲已完成）</span>
            )}
          </span>
          <input
            type="checkbox"
            role="switch"
            aria-label="开启或关闭写作指引"
            data-testid="ghost-toggle"
            checked={ghostEnabled}
            onChange={(event) => onToggleGhost(event.target.checked)}
            className="h-4 w-4"
          />
        </label>
      </div>

      <div ref={scrollRef} className="awc-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && !send.isPending && (
          <div className="rounded-lg bg-zinc-50 p-3 text-xs leading-relaxed text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
            你好，我是写作构思助手。告诉我你的想法或立场，我会按雅思要求构思一篇英文范文并译成中文，连同大纲一起给你；
            确认后，写作时文末会逐句显示灰色中文提示，你把每句的意思自己译成英文、大意相符就推进到下一句（翻译练习，而非抄范文）。开始写作后，也可以随时回来让我调整。
          </div>
        )}
        {messages.map((message) => (
          <div key={message.id} data-testid={`planner-message-${message.role}`}>
            <div
              className={
                message.role === "user"
                  ? "ml-6 rounded-lg bg-zinc-900 px-3 py-2 text-xs leading-relaxed text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "mr-2 rounded-lg bg-zinc-100 px-3 py-2 text-xs leading-relaxed text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
              }
            >
              {message.content}
            </div>
            {message.outline_id && (
              <OutlineCard outlineId={message.outline_id} essayId={essayId} />
            )}
          </div>
        ))}
        {send.isPending && (
          <div className="mr-2 rounded-lg bg-zinc-100 px-3 py-2 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
            助手正在思考…
          </div>
        )}
      </div>

      <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
        {sendError && (
          <p role="alert" className="mb-2 text-xs text-red-600 dark:text-red-400">
            {sendError}
          </p>
        )}
        <textarea
          data-testid="planner-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
          rows={2}
          maxLength={2000}
          placeholder="说说你的想法，例如：我同意大城市公共交通应该免费…"
          className="awc-scroll w-full resize-none rounded-md border border-zinc-300 px-3 py-2 text-xs leading-relaxed focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
        />
        <div className="mt-2 flex justify-end">
          <button
            type="button"
            data-testid="planner-send"
            disabled={send.isPending || draft.trim() === ""}
            onClick={submit}
            className="rounded-md bg-zinc-900 px-4 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {send.isPending ? "发送中…" : "发送"}
          </button>
        </div>
      </div>
    </div>
  );
}
