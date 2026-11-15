"use client";

/**
 * Writing preferences (PRD FR-01, Slice 9): assistance toggles, daily review
 * goal and UI language. Stored server-side in user_profiles.preferences.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getPreferences, patchPreferences } from "@/services/preferences";
import type { PreferencesData } from "@/types/api";

export function PreferencesCard() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preferencesQuery = useQuery({
    queryKey: ["preferences"],
    queryFn: async () => (await getPreferences()).data,
  });

  const save = useMutation({
    mutationFn: async (payload: Partial<PreferencesData>) => patchPreferences(payload),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey: ["preferences"] });
      const previous = queryClient.getQueryData<PreferencesData>(["preferences"]);
      queryClient.setQueryData<PreferencesData>(["preferences"], (old) =>
        old ? { ...old, ...payload } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      setSaved(true);
      setError(null);
    },
    onError: (err, _payload, context) => {
      setSaved(false);
      setError(err instanceof Error ? err.message : "无法保存偏好设置。");
      if (context?.previous) {
        queryClient.setQueryData(["preferences"], context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["preferences"] });
    },
  });

  const preferences = preferencesQuery.data;

  return (
    <section
      aria-label="写作偏好"
      className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="preferences-card"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        写作偏好
      </h2>
      {preferencesQuery.isPending && <p className="mt-3 text-sm text-zinc-500">加载中…</p>}
      {preferences && (
        <div className="mt-3 space-y-3 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              data-testid="pref-grammar"
              checked={preferences.auto_grammar_check}
              onChange={(event) => save.mutate({ auto_grammar_check: event.target.checked })}
              className="h-4 w-4"
            />
            <span className="text-zinc-700 dark:text-zinc-300">自动语法检查</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              data-testid="pref-assist"
              checked={preferences.auto_expression_assist}
              onChange={(event) => save.mutate({ auto_expression_assist: event.target.checked })}
              className="h-4 w-4"
            />
            <span className="text-zinc-700 dark:text-zinc-300">表达辅助</span>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-zinc-500">每日复习目标</span>
            <input
              type="number"
              min={1}
              max={100}
              data-testid="pref-review-goal"
              defaultValue={preferences.daily_review_goal ?? ""}
              onBlur={(event) => {
                const raw = event.target.value;
                save.mutate({ daily_review_goal: raw === "" ? null : Number(raw) });
              }}
              className="mt-1 block w-32 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-zinc-500">界面语言</span>
            <select
              data-testid="pref-language"
              value={preferences.ui_language}
              onChange={(event) => save.mutate({ ui_language: event.target.value as "zh" | "en" })}
              className="mt-1 block rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </label>
          {saved && !save.isPending && (
            <p className="text-xs text-emerald-600 dark:text-emerald-400" data-testid="pref-saved">
              偏好已保存。
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
        </div>
      )}
    </section>
  );
}
