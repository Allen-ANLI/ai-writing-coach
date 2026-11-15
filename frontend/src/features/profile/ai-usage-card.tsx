"use client";

/**
 * AI 用量统计（API Spec §16，Slice 9）：当前用户自己的调用次数、token、
 * 估算费用、按功能分布与 14 天趋势。规则检查不是 LLM 调用，不会出现在此。
 */

import { useQuery } from "@tanstack/react-query";

import { aiUsageByFeature, aiUsageTotals, aiUsageTrends } from "@/services/analytics";

const FEATURE_LABELS: Record<string, string> = {
  grammar_deep_check: "语法深度检查",
  teaching: "错误详细讲解",
  grammar_validate: "自改验证",
  expression_polish: "表达润色",
  translation: "中译英",
  learning_extract: "表达提取",
  review_judge: "复习判分",
  weakness_practice: "弱项练习",
  ielts_evaluate_task1: "IELTS Task 1 评分",
  ielts_evaluate_task2: "IELTS Task 2 评分",
  general_evaluate: "通用评分",
  rewrite: "改写",
  outline_generate: "大纲生成",
  planner_chat: "构思对话",
  study_plan: "学习计划",
};

export function AiUsageCard() {
  const totalsQuery = useQuery({
    queryKey: ["ai-usage-totals"],
    queryFn: async () => (await aiUsageTotals()).data,
  });
  const featuresQuery = useQuery({
    queryKey: ["ai-usage-features"],
    queryFn: async () => (await aiUsageByFeature()).data.items,
  });
  const trendsQuery = useQuery({
    queryKey: ["ai-usage-trends"],
    queryFn: async () => (await aiUsageTrends()).data.items,
  });

  const totals = totalsQuery.data;
  const maxCalls = Math.max(1, ...(trendsQuery.data ?? []).map((point) => point.calls));

  return (
    <section
      aria-label="AI 用量"
      className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="ai-usage-card"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        AI 用量
      </h2>
      {totalsQuery.isPending && <p className="mt-3 text-sm text-zinc-500">加载中…</p>}
      {totals && (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4" data-testid="usage-totals">
            <div>
              <dt className="text-xs text-zinc-500">AI 调用次数</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{totals.total_calls}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Token（输入/输出）</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                {totals.input_tokens}/{totals.output_tokens}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">估算费用</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                ${totals.estimated_cost.toFixed(4)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">失败次数</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{totals.error_calls}</dd>
            </div>
          </dl>

          {featuresQuery.data && featuresQuery.data.length > 0 && (
            <ul className="mt-4 space-y-1 text-xs text-zinc-600 dark:text-zinc-400" data-testid="usage-features">
              {featuresQuery.data.map((feature) => (
                <li key={feature.feature} className="flex justify-between">
                  <span>{FEATURE_LABELS[feature.feature] ?? feature.feature}</span>
                  <span>{feature.calls} 次 · ${feature.estimated_cost.toFixed(4)}</span>
                </li>
              ))}
            </ul>
          )}

          {trendsQuery.data && (
            <div className="mt-4" data-testid="usage-trend">
              <p className="text-xs text-zinc-500">最近 14 天</p>
              <div className="mt-1 flex h-12 items-end gap-0.5">
                {trendsQuery.data.map((point) => (
                  <div
                    key={point.date}
                    title={`${point.date}：${point.calls} 次调用`}
                    className="flex-1 rounded-t bg-zinc-300 dark:bg-zinc-700"
                    style={{ height: `${(point.calls / maxCalls) * 100}%`, minHeight: point.calls > 0 ? 4 : 1 }}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
