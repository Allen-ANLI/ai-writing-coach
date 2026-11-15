"use client";

/**
 * 学习中心（PRD FR-05/FR-07，API Spec §10–11）：间隔重复翻译练习
 * （中文提示 → 英文作答）、统计摘要与个人弱项画像。调度由服务端 SM-2 决定。
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dueReviews, learningSummary, submitReview, weaknesses } from "@/services/learning";
import { createWorkflow, getWorkflow, resumeWorkflow } from "@/services/workflows";
import type { ReviewPrompt, ReviewResultData, StudyPlanResult } from "@/types/api";
import { PlansCard } from "@/features/learning/plans-card";

const CATEGORY_LABELS: Record<string, string> = {
  grammar: "语法",
  spelling: "拼写",
  vocabulary: "词汇",
  collocation: "搭配",
  naturalness: "地道性",
  style: "风格",
};

const TASK_TYPE_LABELS: Record<string, string> = {
  review: "复习",
  practice: "练习",
  writing: "写作",
};

const WORKFLOW_STATUS_LABELS: Record<string, string> = {
  running: "运行中",
  awaiting_confirmation: "等待确认",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export function LearningPage() {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<ReviewResultData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [plannerGoal, setPlannerGoal] = useState("");
  const [plannerWorkflowId, setPlannerWorkflowId] = useState<string | null>(null);
  const [plannerError, setPlannerError] = useState<string | null>(null);

  const summaryQuery = useQuery({
    queryKey: ["learning-summary"],
    queryFn: async () => (await learningSummary()).data,
  });
  const dueQuery = useQuery({
    queryKey: ["learning-due"],
    queryFn: async () => (await dueReviews()).data,
  });
  const weaknessQuery = useQuery({
    queryKey: ["weaknesses"],
    queryFn: async () => (await weaknesses()).data.items,
  });

  const plannerQuery = useQuery({
    queryKey: ["study-planner-workflow", plannerWorkflowId],
    queryFn: async () => (await getWorkflow(plannerWorkflowId as string)).data,
    enabled: plannerWorkflowId !== null,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1500 : false),
  });

  const startPlanner = useMutation({
    mutationFn: async () =>
      createWorkflow({
        workflow_type: "personalized_study_planner",
        input: { goal: plannerGoal.trim() === "" ? null : plannerGoal.trim() },
      }),
    onSuccess: (response) => {
      setPlannerWorkflowId(response.data.workflow_id);
      setPlannerError(null);
    },
    onError: (err) => setPlannerError(err instanceof Error ? err.message : "无法启动学习规划。"),
  });

  const resumePlanner = useMutation({
    mutationFn: async (action: "confirm" | "reject") =>
      resumeWorkflow(plannerWorkflowId as string, action),
    onSuccess: () => {
      setPlannerError(null);
      void queryClient.invalidateQueries({ queryKey: ["study-planner-workflow", plannerWorkflowId] });
      void queryClient.invalidateQueries({ queryKey: ["learning-plans"] });
      void queryClient.invalidateQueries({ queryKey: ["learning-tasks"] });
    },
    onError: (err) => setPlannerError(err instanceof Error ? err.message : "操作失败。"),
  });

  const planner = plannerQuery.data ?? null;
  const studyPlan = (planner?.result_json?.plan ?? null) as StudyPlanResult | null;

  const current: ReviewPrompt | null = dueQuery.data?.items[0] ?? null;

  const reviewMutation = useMutation({
    mutationFn: async () => {
      if (!current) {
        throw new Error("没有可复习的内容。");
      }
      return (await submitReview(current.expression_id, answer.trim())).data;
    },
    onSuccess: (data) => {
      setResult(data);
      setAnswer("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["learning-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["weaknesses"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "复习提交失败。"),
  });

  const nextReview = () => {
    setResult(null);
    void queryClient.invalidateQueries({ queryKey: ["learning-due"] });
  };

  const summary = summaryQuery.data;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        学习中心
      </h1>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
        看中文写英文，任何自然正确的英文答案都会被接受。间隔重复为你安排复习。
      </p>

      {summary && (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="learning-summary">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">表达总数</p>
            <p className="text-xl font-semibold">{summary.total_expressions}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">待复习</p>
            <p className="text-xl font-semibold" data-testid="due-count">{summary.due_now}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">已掌握</p>
            <p className="text-xl font-semibold">{summary.mastered}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">今日已复习</p>
            <p className="text-xl font-semibold">{summary.reviewed_today}</p>
          </div>
        </div>
      )}

      <section className="mt-8" aria-label="翻译练习">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          翻译练习
        </h2>

        {dueQuery.isPending && <p className="mt-3 text-sm text-zinc-500">复习加载中…</p>}

        {!dueQuery.isPending && !current && !result && (
          <p data-testid="no-reviews" className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
            当前没有待复习内容。去编辑器或知识库收集表达吧。
          </p>
        )}

        {current && !result && (
          <form
            className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
            data-testid="review-card"
            onSubmit={(event) => {
              event.preventDefault();
              reviewMutation.mutate();
            }}
          >
            <p className="text-xs text-zinc-400">
              {current.topic ?? "综合"} · 第 {current.review_count + 1} 次复习
            </p>
            <p className="mt-2 text-lg font-medium text-zinc-900 dark:text-zinc-100" data-testid="review-prompt">
              {current.chinese_meaning ?? current.usage_context ?? "翻译这个表达"}
            </p>
            <label className="mt-3 block text-sm">
              <span className="text-xs font-medium text-zinc-500">你的英文翻译</span>
              <input
                data-testid="review-answer"
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                maxLength={2000}
                className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                autoFocus
              />
            </label>
            {error && (
              <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}
            <button
              type="submit"
              data-testid="review-submit"
              disabled={reviewMutation.isPending || answer.trim() === ""}
              className="mt-3 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {reviewMutation.isPending ? "判分中…" : "检查答案"}
            </button>
          </form>
        )}

        {result && (
          <div
            className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
            data-testid="review-result"
          >
            <p
              className={`text-sm font-semibold ${
                result.is_correct
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {result.is_correct ? "正确 — 做得好。" : "还差一点。"}
            </p>
            <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
              参考表达：<strong>{result.reference_expression}</strong>
            </p>
            {result.feedback && (
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{result.feedback}</p>
            )}
            <p className="mt-1 text-xs text-zinc-400">
              下次复习：{result.interval_days} 天后 · 连续正确 {result.streak_count} 次
            </p>
            <button
              type="button"
              data-testid="review-next"
              onClick={nextReview}
              className="mt-3 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
            >
              下一个
            </button>
          </div>
        )}
      </section>

      <section className="mt-8" aria-label="弱项画像">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          你的高频弱项
        </h2>
        {weaknessQuery.data && weaknessQuery.data.length === 0 && (
          <p className="mt-3 text-sm text-zinc-500">
            暂未发现高频弱项 — 继续写作吧。
          </p>
        )}
        <ul className="mt-3 space-y-2" data-testid="weakness-list">
          {weaknessQuery.data?.map((weakness) => (
            <li
              key={`${weakness.category}-${weakness.sub_category}`}
              className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
            >
              <span className="font-medium text-zinc-800 dark:text-zinc-200">
                {CATEGORY_LABELS[weakness.category] ?? weakness.category}
                {weakness.sub_category ? ` · ${weakness.sub_category}` : ""}
              </span>
              <span className="text-xs text-zinc-500">
                出现 {weakness.total_occurrences} 次
              </span>
            </li>
          ))}
        </ul>
      </section>

      <PlansCard />

      <section className="mt-8" aria-label="学习规划" data-testid="study-planner">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          个性化学习规划
        </h2>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          AI 工作流结合你的弱项画像与掌握情况给出学习建议。确认前不会保存任何内容。
        </p>

        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="text-xs font-medium text-zinc-500">目标（可选）</span>
            <input
              data-testid="planner-goal"
              value={plannerGoal}
              onChange={(event) => setPlannerGoal(event.target.value)}
              maxLength={200}
              placeholder="例如：三个月内达到 7 分"
              className="mt-1 block w-64 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <button
            type="button"
            data-testid="generate-plan"
            disabled={startPlanner.isPending || planner?.status === "running"}
            onClick={() => startPlanner.mutate()}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {startPlanner.isPending || planner?.status === "running" ? "规划中…" : "生成学习计划"}
          </button>
        </div>

        {plannerError && (
          <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{plannerError}</p>
        )}

        {planner && (
          <p className="mt-2 text-xs text-zinc-400" data-testid="plan-status">
            状态：{WORKFLOW_STATUS_LABELS[planner.status] ?? planner.status}
            {planner.current_step ? ` · 步骤：${planner.current_step}` : ""}
          </p>
        )}
        {planner?.status === "failed" && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">{planner.error_message}</p>
        )}

        {planner?.status === "awaiting_confirmation" && studyPlan && (
          <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
            <p className="text-xs font-medium text-zinc-500">
              重点：{studyPlan.focus_areas.join("、")}
            </p>
            <ul className="mt-2 space-y-2" data-testid="plan-suggestions">
              {studyPlan.suggestions.map((suggestion, index) => (
                <li key={`${suggestion.title}-${index}`} className="text-sm">
                  <p className="font-medium text-zinc-800 dark:text-zinc-200">
                    [{TASK_TYPE_LABELS[suggestion.task_type] ?? suggestion.task_type}] {suggestion.title}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{suggestion.description}</p>
                </li>
              ))}
            </ul>
            <div className="mt-3 flex gap-3">
              <button
                type="button"
                data-testid="confirm-plan"
                disabled={resumePlanner.isPending}
                onClick={() => resumePlanner.mutate("confirm")}
                className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
              >
                确认计划
              </button>
              <button
                type="button"
                data-testid="reject-plan"
                disabled={resumePlanner.isPending}
                onClick={() => resumePlanner.mutate("reject")}
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              >
                拒绝
              </button>
            </div>
          </div>
        )}

        {planner?.status === "completed" && (
          <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400" data-testid="plan-done">
            {planner.result_json?.outcome &&
            (planner.result_json.outcome as Record<string, unknown>).rejected
              ? "计划已拒绝。"
              : "计划已确认 — 按建议开始练习吧。"}
          </p>
        )}
      </section>
    </main>
  );
}
