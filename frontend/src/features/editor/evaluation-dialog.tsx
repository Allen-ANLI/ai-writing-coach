"use client";

/**
 * 写后评分与改写（PRD FR-09，ADR-016/024）：评分绑定当前文本的不可变快照，
 * 分数明确标注为估分；改写先预览，仅在用户明确接受后应用。
 * 写作过程中不会自动运行这里的任何功能。
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import { ApiClientError } from "@/lib/api-client";
import { createSnapshot, getVersion } from "@/services/documents";
import {
  acceptRewrite,
  deleteEvaluation,
  getEvaluation,
  getRewrite,
  listEvaluations,
  queueEvaluation,
  queueRewrite,
} from "@/services/evaluations";
import type {
  EvaluationData,
  ModificationLevel,
  TipTapDocument,
  WritingType,
} from "@/types/api";
import type { SaveStatus } from "@/features/editor/use-autosave";

const CRITERION_LABELS: Record<string, string> = {
  task_achievement: "任务完成情况",
  task_response: "任务回应",
  coherence_cohesion: "连贯与衔接",
  lexical_resource: "词汇丰富度",
  grammatical_range_accuracy: "语法多样性与准确性",
  content: "内容",
  organization: "结构",
  language: "语言",
};

const LEVEL_LABELS: Record<ModificationLevel, string> = {
  level_1: "级别 1 — 仅语法与拼写",
  level_2: "级别 2 — 含用词优化",
  level_3: "级别 3 — 含句子流畅度",
  level_4: "级别 4 — 含结构与衔接",
};

const STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  processing: "处理中",
  completed: "已完成",
  failed: "失败",
};

function isPending(status: string): boolean {
  return status === "queued" || status === "processing";
}

export function EvaluationDialog({
  essayId,
  writingType,
  serverRevision,
  saveStatus,
  onClose,
  onRewriteAccepted,
}: {
  essayId: string;
  writingType: WritingType;
  serverRevision: number;
  saveStatus: SaveStatus;
  onClose: () => void;
  onRewriteAccepted: (content: TipTapDocument, revision: number) => void;
}) {
  const queryClient = useQueryClient();
  const [activeEvaluationId, setActiveEvaluationId] = useState<string | null>(null);
  const [activeRewriteId, setActiveRewriteId] = useState<string | null>(null);
  const [level, setLevel] = useState<ModificationLevel>("level_2");
  const [actionError, setActionError] = useState<string | null>(null);

  const evaluationsQuery = useQuery({
    queryKey: ["evaluations", essayId],
    queryFn: async () => (await listEvaluations(essayId)).data.items,
    refetchInterval: (query) =>
      query.state.data?.some((item) => isPending(item.status)) ? 1500 : false,
  });

  const evaluationQuery = useQuery({
    queryKey: ["evaluation", activeEvaluationId],
    queryFn: async () => (await getEvaluation(activeEvaluationId as string)).data,
    enabled: activeEvaluationId !== null,
    refetchInterval: (query) =>
      query.state.data && isPending(query.state.data.status) ? 1500 : false,
  });

  const rewriteQuery = useQuery({
    queryKey: ["rewrite", activeRewriteId],
    queryFn: async () => (await getRewrite(activeRewriteId as string)).data,
    enabled: activeRewriteId !== null,
    refetchInterval: (query) =>
      query.state.data && isPending(query.state.data.status) ? 1500 : false,
  });

  const errorMessage = (error: unknown, fallback: string) =>
    error instanceof ApiClientError ? error.message : fallback;

  const runEvaluation = useMutation({
    mutationFn: async () => {
      const snapshot = await createSnapshot(
        essayId,
        { source_revision: serverRevision, version_type: "checkpoint", label: "评分前存档" },
        crypto.randomUUID(),
      );
      const ielts = writingType === "ielts_task1" || writingType === "ielts_task2";
      return queueEvaluation(essayId, {
        version_id: snapshot.data.id,
        evaluation_type: ielts ? "ielts" : "general",
        task_type: ielts ? (writingType === "ielts_task1" ? "task1" : "task2") : null,
      });
    },
    onSuccess: (response) => {
      setActiveEvaluationId(response.data.evaluation_id);
      setActiveRewriteId(null);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["evaluations", essayId] });
      void queryClient.invalidateQueries({ queryKey: ["versions", essayId] });
    },
    onError: (error) => setActionError(errorMessage(error, "无法启动评分。")),
  });

  const generateRewrite = useMutation({
    mutationFn: async () => queueRewrite(activeEvaluationId as string, level),
    onSuccess: (response) => {
      setActiveRewriteId(response.data.rewrite_id);
      setActionError(null);
    },
    onError: (error) => setActionError(errorMessage(error, "无法启动改写。")),
  });

  const accept = useMutation({
    mutationFn: async () => {
      const response = await acceptRewrite(activeRewriteId as string, serverRevision);
      const version = await getVersion(essayId, response.data.result_version_id);
      return { response, version };
    },
    onSuccess: ({ response, version }) => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["versions", essayId] });
      void queryClient.invalidateQueries({ queryKey: ["evaluations", essayId] });
      onRewriteAccepted(version.data.content_json, response.data.server_revision);
    },
    onError: (error) => setActionError(errorMessage(error, "无法接受改写。")),
  });

  const removeEvaluation = useMutation({
    mutationFn: async (evaluationId: string) => deleteEvaluation(evaluationId),
    onSuccess: (_data, evaluationId) => {
      if (activeEvaluationId === evaluationId) {
        setActiveEvaluationId(null);
        setActiveRewriteId(null);
      }
      void queryClient.invalidateQueries({ queryKey: ["evaluations", essayId] });
    },
    onError: (error) => setActionError(errorMessage(error, "无法删除该评分。")),
  });

  const active: EvaluationData | null = evaluationQuery.data ?? null;
  const rewrite = rewriteQuery.data ?? null;

  return (
    <Dialog title="评分与改进" onClose={onClose}>
      <div data-testid="evaluation-dialog" className="awc-scroll max-h-[70vh] space-y-4 overflow-y-auto pr-1">
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          评分针对文本的不可变快照。AI 分数为估分，不是官方 IELTS 成绩。
          改写只有在你接受后才会应用。
        </p>

        {saveStatus !== "saved" && (
          <p className="text-xs text-amber-600 dark:text-amber-400" data-testid="evaluation-save-hint">
            请先保存最新修改（Ctrl+S），评分才会包含这些内容。
          </p>
        )}

        <button
          type="button"
          data-testid="run-evaluation"
          disabled={runEvaluation.isPending || saveStatus !== "saved"}
          onClick={() => runEvaluation.mutate()}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {runEvaluation.isPending ? "启动中…" : "评分当前文本"}
        </button>

        {actionError && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">{actionError}</p>
        )}

        {active && (
          <section className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800" data-testid="evaluation-detail">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium uppercase tracking-wide text-zinc-400" data-testid="evaluation-status">
                {STATUS_LABELS[active.status] ?? active.status}
              </span>
              {active.status === "completed" && active.overall_band !== null && (
                <span className="text-lg font-semibold text-zinc-900 dark:text-zinc-50" data-testid="evaluation-band">
                  {active.overall_band} 分
                </span>
              )}
              {active.is_estimate && active.status === "completed" && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-950 dark:text-amber-300" data-testid="estimated-badge">
                  AI 估分
                </span>
              )}
            </div>

            {isPending(active.status) && (
              <p className="mt-2 text-sm text-zinc-500">正在评分…</p>
            )}
            {active.status === "failed" && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">{active.error_message}</p>
            )}

            {active.status === "completed" && active.criteria_scores && (
              <ul className="mt-3 space-y-2" data-testid="criteria-list">
                {Object.entries(active.criteria_scores).map(([name, score]) => (
                  <li key={name} className="text-sm">
                    <p className="font-medium text-zinc-800 dark:text-zinc-200">
                      {CRITERION_LABELS[name] ?? name}：{score.band}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">{score.feedback}</p>
                  </li>
                ))}
              </ul>
            )}

            {active.status === "completed" && active.feedback_json && (
              <div className="mt-3 text-sm text-zinc-600 dark:text-zinc-300">
                <p>{active.feedback_json.overall_feedback}</p>
              </div>
            )}

            {active.status === "completed" && (
              <div className="mt-4 border-t border-zinc-100 pt-3 dark:border-zinc-800">
                <label className="block text-xs font-medium text-zinc-500">
                  改写级别
                  <select
                    data-testid="rewrite-level"
                    value={level}
                    onChange={(event) => setLevel(event.target.value as ModificationLevel)}
                    className="mt-1 block w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  >
                    {(Object.keys(LEVEL_LABELS) as ModificationLevel[]).map((value) => (
                      <option key={value} value={value}>{LEVEL_LABELS[value]}</option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  data-testid="generate-rewrite"
                  disabled={generateRewrite.isPending || (rewrite !== null && isPending(rewrite.status))}
                  onClick={() => generateRewrite.mutate()}
                  className="mt-2 rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                >
                  {generateRewrite.isPending ? "启动中…" : "生成改写"}
                </button>
              </div>
            )}
          </section>
        )}

        {rewrite && (
          <section className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800" data-testid="rewrite-section">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-400" data-testid="rewrite-status">
              改写 · {STATUS_LABELS[rewrite.status] ?? rewrite.status}
            </p>
            {isPending(rewrite.status) && <p className="mt-2 text-sm text-zinc-500">正在改写…</p>}
            {rewrite.status === "failed" && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">{rewrite.error_message}</p>
            )}
            {rewrite.status === "completed" && (
              <>
                {rewrite.change_summary && (
                  <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{rewrite.change_summary}</p>
                )}
                <p className="awc-scroll mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-md bg-zinc-50 p-2 text-sm text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200" data-testid="rewrite-result">
                  {rewrite.result_plain_text}
                </p>
                {rewrite.result_version_id === null ? (
                  <button
                    type="button"
                    data-testid="accept-rewrite"
                    disabled={accept.isPending || saveStatus !== "saved"}
                    onClick={() => accept.mutate()}
                    className="mt-3 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                  >
                    {accept.isPending ? "应用中…" : "接受改写"}
                  </button>
                ) : (
                  <p className="mt-3 text-xs text-emerald-600 dark:text-emerald-400">
                    已接受 — 已应用到你的作文。
                  </p>
                )}
              </>
            )}
          </section>
        )}

        <section aria-label="评分历史">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">历史评分</h3>
          {evaluationsQuery.data && evaluationsQuery.data.length === 0 && (
            <p className="mt-2 text-sm text-zinc-500">还没有评分记录。</p>
          )}
          <ul className="mt-2 space-y-2" data-testid="evaluation-history">
            {evaluationsQuery.data?.map((item) => (
              <li
                key={item.id}
                data-testid="evaluation-item"
                className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
              >
                <button
                  type="button"
                  onClick={() => {
                    setActiveEvaluationId(item.id);
                    setActiveRewriteId(null);
                  }}
                  className="text-left text-zinc-700 hover:underline dark:text-zinc-300"
                >
                  {item.evaluation_type === "ielts" ? `IELTS ${item.task_type ?? ""}` : "通用评分"}
                  {item.status === "completed" && item.overall_band !== null
                    ? ` — ${item.overall_band} 分`
                    : ` — ${STATUS_LABELS[item.status] ?? item.status}`}
                </button>
                <button
                  type="button"
                  aria-label="删除评分"
                  data-testid="delete-evaluation"
                  onClick={() => removeEvaluation.mutate(item.id)}
                  className="text-xs text-zinc-400 hover:text-red-600 dark:hover:text-red-400"
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </Dialog>
  );
}
