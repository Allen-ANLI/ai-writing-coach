"use client";

/**
 * 错误与优化记录（ADR-026）：已完成作文的回顾视图，
 * 分类展示语法错误（writing_issues）与表达优化（expression_suggestions）。
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import { listEssaySuggestions } from "@/services/expressions";
import { listIssues } from "@/services/grammar";

const CATEGORY_LABELS: Record<string, string> = {
  grammar: "语法",
  spelling: "拼写",
  vocabulary: "词汇",
  collocation: "搭配",
  naturalness: "表达自然度",
  style: "风格",
};

const ISSUE_STATUS: Record<string, { label: string; className: string }> = {
  resolved: {
    label: "已解决",
    className: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  },
  ignored: {
    label: "已忽略",
    className: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
  },
  detected: {
    label: "待处理",
    className: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  },
  stale: {
    label: "已过期",
    className: "bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500",
  },
};

export function RecordsDialog({ essayId, onClose }: { essayId: string; onClose: () => void }) {
  const [tab, setTab] = useState<"grammar" | "expression">("grammar");

  const issuesQuery = useQuery({
    queryKey: ["essay-issues", essayId],
    queryFn: async () => (await listIssues(essayId)).data.items,
  });
  const suggestionsQuery = useQuery({
    queryKey: ["essay-suggestions", essayId],
    queryFn: async () => (await listEssaySuggestions(essayId)).data.items,
  });

  const issues = (issuesQuery.data ?? []).filter((issue) => issue.status !== "stale");
  const suggestions = suggestionsQuery.data ?? [];

  return (
    <Dialog title="错误与优化记录" onClose={onClose}>
      <div data-testid="records-dialog" className="space-y-3">
        <div className="flex gap-2" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "grammar"}
            data-testid="records-tab-grammar"
            onClick={() => setTab("grammar")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              tab === "grammar"
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "border border-zinc-300 text-zinc-600 dark:border-zinc-700 dark:text-zinc-300"
            }`}
          >
            语法错误（{issues.length}）
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "expression"}
            data-testid="records-tab-expression"
            onClick={() => setTab("expression")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              tab === "expression"
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "border border-zinc-300 text-zinc-600 dark:border-zinc-700 dark:text-zinc-300"
            }`}
          >
            表达优化（{suggestions.length}）
          </button>
        </div>

        {tab === "grammar" && (
          <div className="awc-scroll max-h-[55vh] space-y-2 overflow-y-auto" data-testid="grammar-records">
            {issuesQuery.isPending && <p className="text-sm text-zinc-500">加载中…</p>}
            {!issuesQuery.isPending && issues.length === 0 && (
              <p className="text-sm text-zinc-500">这篇作文没有语法错误记录。</p>
            )}
            {issues.map((issue) => {
              const status = ISSUE_STATUS[issue.status] ?? ISSUE_STATUS.detected;
              return (
                <div
                  key={issue.id}
                  data-testid="grammar-record"
                  className="rounded-lg border border-zinc-200 p-2.5 dark:border-zinc-800"
                >
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
                      {CATEGORY_LABELS[issue.category] ?? issue.category}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${status.className}`}>
                      {status.label}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">
                    <span className="text-red-600 line-through dark:text-red-400">
                      {issue.anchor_text}
                    </span>
                  </p>
                  {issue.short_explanation && (
                    <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                      {issue.short_explanation}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {tab === "expression" && (
          <div className="awc-scroll max-h-[55vh] space-y-2 overflow-y-auto" data-testid="expression-records">
            {suggestionsQuery.isPending && <p className="text-sm text-zinc-500">加载中…</p>}
            {!suggestionsQuery.isPending && suggestions.length === 0 && (
              <p className="text-sm text-zinc-500">这篇作文没有表达优化记录。</p>
            )}
            {suggestions.map((suggestion) => {
              const accepted = suggestion.items.find((item) => item.status === "accepted");
              return (
                <div
                  key={suggestion.id}
                  data-testid="expression-record"
                  className="rounded-lg border border-zinc-200 p-2.5 dark:border-zinc-800"
                >
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                      {suggestion.kind === "polish" ? "润色" : "翻译"}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        accepted
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                          : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                      }`}
                    >
                      {accepted ? "已采用" : "未替换"}
                    </span>
                  </div>
                  <p className="mt-1 text-sm">
                    <span className="text-zinc-500 line-through dark:text-zinc-400">
                      {suggestion.selected_text}
                    </span>
                    {accepted && (
                      <>
                        <span className="mx-1 text-zinc-400">→</span>
                        <span className="font-medium text-emerald-700 dark:text-emerald-400">
                          {accepted.english_text}
                        </span>
                      </>
                    )}
                  </p>
                  {accepted?.usage_note && (
                    <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
                      {accepted.usage_note}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Dialog>
  );
}
