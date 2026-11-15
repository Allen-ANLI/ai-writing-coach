"use client";

/**
 * 写作会话控件（API Spec §5，SD §10；ADR-024）：
 * 打开编辑器时已由 writing-editor 自动创建辅助学习会话；此处可切换
 * 独立写作/模拟考试。enabled_features 由后端派生并门控辅助 UI。
 * 写作中无提交按钮：评分/改写是写后动作（Slice 7）。
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import { ApiClientError } from "@/lib/api-client";
import { cancelSession, createSession, listSessions } from "@/services/sessions";
import type { ActivityType, SessionData, WritingMode } from "@/types/api";

const ACTIVITY_LABELS: Record<ActivityType, string> = {
  free_writing: "自由写作",
  practice: "练习",
  mock_exam: "模拟考试",
};

function formatRemaining(deadline: string): string {
  const ms = new Date(deadline).getTime() - Date.now();
  if (ms <= 0) {
    return "时间到";
  }
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function useCountdown(deadline: string | null): string | null {
  // The interval only triggers re-renders; the value is derived at render time.
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!deadline) {
      return;
    }
    const timer = setInterval(() => setTick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [deadline]);
  return deadline ? formatRemaining(deadline) : null;
}

export function SessionControls({
  essayId,
}: {
  essayId: string;
}) {
  const queryClient = useQueryClient();
  const [startOpen, setStartOpen] = useState(false);
  const [mode, setMode] = useState<WritingMode>("assisted");
  const [activity, setActivity] = useState<ActivityType>("practice");
  const [taskType, setTaskType] = useState<"task1" | "task2">("task2");
  const [duration, setDuration] = useState(40);
  const [error, setError] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["sessions", essayId],
    queryFn: async () => (await listSessions(essayId)).data.items,
  });
  const sessions = sessionsQuery.data ?? [];
  const active = sessions.find((session) => session.status === "active") ?? null;
  const latestSubmitted = sessions.find((session) => session.status === "submitted") ?? null;

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["sessions", essayId] });
    void queryClient.invalidateQueries({ queryKey: ["essay", essayId] });
  };

  const startMutation = useMutation({
    mutationFn: async () =>
      createSession(essayId, {
        mode,
        activity_type: activity,
        exam_config:
          activity === "mock_exam"
            ? { exam_type: "IELTS", task_type: taskType, duration_minutes: duration }
            : null,
      }),
    onSuccess: () => {
      setStartOpen(false);
      setError(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiClientError ? err.message : "无法启动会话。"),
  });

  const cancelMutation = useMutation({
    mutationFn: async (session: SessionData) => cancelSession(session.id),
    onSuccess: invalidate,
    onError: () => setError("无法取消会话。"),
  });

  const countdown = useCountdown(active?.deadline_at ?? null);

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 px-4 py-1.5 text-xs dark:border-zinc-800">
      {sessionsQuery.isPending && <span className="text-zinc-400">会话加载中…</span>}

      {!sessionsQuery.isPending && !active && (
        <>
          {latestSubmitted && (
            <span
              data-testid="session-submitted-chip"
              className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
            >
              已提交 {new Date(latestSubmitted.submitted_at ?? "").toLocaleString()}
            </span>
          )}
          <button
            type="button"
            data-testid="start-session"
            onClick={() => {
              setError(null);
              setStartOpen(true);
            }}
            className="rounded-md bg-zinc-900 px-2.5 py-1 font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            开始写作会话
          </button>
        </>
      )}

      {active && (
        <>
          <span
            data-testid="session-mode-chip"
            className={`rounded-full px-2 py-0.5 font-medium ${
              active.mode === "assisted"
                ? "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300"
                : "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300"
            }`}
          >
            {active.mode === "assisted" ? "辅助学习" : "独立写作"}
          </span>
          <span className="text-zinc-500 dark:text-zinc-400">
            {ACTIVITY_LABELS[active.activity_type]}
          </span>
          {countdown && (
            <span
              data-testid="exam-countdown"
              className="font-mono font-medium text-zinc-700 dark:text-zinc-300"
            >
              ⏱ {countdown}
            </span>
          )}
          {active.mode === "independent" && (
            <span
              data-testid="independent-notice"
              className="text-zinc-500 dark:text-zinc-400"
            >
              本会话已关闭实时辅助。
            </span>
          )}
          <span className="ml-auto flex items-center gap-2">
            <button
              type="button"
              data-testid="cancel-session"
              onClick={() => cancelMutation.mutate(active)}
              className="rounded px-2 py-1 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            >
              取消会话
            </button>
          </span>
        </>
      )}

      {error && (
        <span role="alert" data-testid="session-error" className="w-full text-red-600 dark:text-red-400">
          {error}
        </span>
      )}

      {startOpen && (
        <Dialog title="开始写作会话" onClose={() => setStartOpen(false)}>
          <div className="space-y-4">
            <fieldset>
              <legend className="text-xs font-medium text-zinc-500 dark:text-zinc-400">模式</legend>
              <div className="mt-2 space-y-2">
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="radio"
                    name="session-mode"
                    data-testid="mode-assisted"
                    checked={mode === "assisted"}
                    onChange={() => setMode("assisted")}
                    className="mt-0.5"
                  />
                  <span>
                    <strong>辅助学习</strong> — 写作时提供实时语法反馈与 AI 辅助。
                  </span>
                </label>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="radio"
                    name="session-mode"
                    data-testid="mode-independent"
                    checked={mode === "independent"}
                    onChange={() => setMode("independent")}
                    className="mt-0.5"
                  />
                  <span>
                    <strong>独立写作</strong> — 无实时辅助，提交后进行 AI 评分。
                  </span>
                </label>
              </div>
            </fieldset>

            <label className="block text-sm">
              <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">活动类型</span>
              <select
                data-testid="activity-type"
                value={activity}
                onChange={(event) => setActivity(event.target.value as ActivityType)}
                className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              >
                <option value="free_writing">自由写作</option>
                <option value="practice">练习</option>
                <option value="mock_exam">模拟考试（计时）</option>
              </select>
            </label>

            {activity === "mock_exam" && (
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">任务</span>
                  <select
                    data-testid="exam-task"
                    value={taskType}
                    onChange={(event) => setTaskType(event.target.value as "task1" | "task2")}
                    className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  >
                    <option value="task1">Task 1</option>
                    <option value="task2">Task 2</option>
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    分钟数
                  </span>
                  <input
                    type="number"
                    data-testid="exam-duration"
                    min={1}
                    max={180}
                    value={duration}
                    onChange={(event) => setDuration(Number(event.target.value))}
                    className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                  />
                </label>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setStartOpen(false)}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                取消
              </button>
              <button
                type="button"
                data-testid="confirm-start-session"
                disabled={startMutation.isPending}
                onClick={() => startMutation.mutate()}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                {startMutation.isPending ? "启动中…" : "开始会话"}
              </button>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}
