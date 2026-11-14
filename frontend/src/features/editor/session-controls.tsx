"use client";

/**
 * Writing session controls (API Spec §5, SD §10). Two modes only; the
 * enabled_features map comes from the backend and gates assistance UI.
 * Submit requires a clean save state so expected_server_revision is exact.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import { ApiClientError } from "@/lib/api-client";
import { cancelSession, createSession, listSessions, submitSession } from "@/services/sessions";
import type { ActivityType, SessionData, WritingMode } from "@/types/api";
import type { SaveStatus } from "@/features/editor/use-autosave";

const ACTIVITY_LABELS: Record<ActivityType, string> = {
  free_writing: "Free writing",
  practice: "Practice",
  mock_exam: "Mock exam",
};

function formatRemaining(deadline: string): string {
  const ms = new Date(deadline).getTime() - Date.now();
  if (ms <= 0) {
    return "Time elapsed";
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
  serverRevision,
  saveStatus,
}: {
  essayId: string;
  serverRevision: number;
  saveStatus: SaveStatus;
}) {
  const queryClient = useQueryClient();
  const [startOpen, setStartOpen] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
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
      setError(err instanceof ApiClientError ? err.message : "Could not start the session."),
  });

  const cancelMutation = useMutation({
    mutationFn: async (session: SessionData) => cancelSession(session.id),
    onSuccess: invalidate,
    onError: () => setError("Could not cancel the session."),
  });

  const submitMutation = useMutation({
    mutationFn: async (session: SessionData) =>
      submitSession(
        session.id,
        { expected_server_revision: serverRevision },
        crypto.randomUUID(),
      ),
    onSuccess: () => {
      setConfirmSubmit(false);
      setError(null);
      invalidate();
    },
    onError: (err) => {
      setConfirmSubmit(false);
      setError(
        err instanceof ApiClientError && err.status === 409
          ? "The document changed. Save your edits and submit again."
          : err instanceof ApiClientError
            ? err.message
            : "Could not submit the essay.",
      );
    },
  });

  const countdown = useCountdown(active?.deadline_at ?? null);
  const clean = saveStatus === "saved";

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 px-4 py-1.5 text-xs dark:border-zinc-800">
      {sessionsQuery.isPending && <span className="text-zinc-400">Loading session…</span>}

      {!sessionsQuery.isPending && !active && (
        <>
          {latestSubmitted && (
            <span
              data-testid="session-submitted-chip"
              className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
            >
              Submitted {new Date(latestSubmitted.submitted_at ?? "").toLocaleString()}
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
            Start writing session
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
            {active.mode === "assisted" ? "Assisted learning" : "Independent writing"}
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
              Real-time assistance is disabled for this session.
            </span>
          )}
          <span className="ml-auto flex items-center gap-2">
            <button
              type="button"
              data-testid="cancel-session"
              onClick={() => cancelMutation.mutate(active)}
              className="rounded px-2 py-1 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="button"
              data-testid="submit-session"
              disabled={!clean || submitMutation.isPending}
              onClick={() => {
                setError(null);
                setConfirmSubmit(true);
              }}
              className="rounded-md bg-zinc-900 px-2.5 py-1 font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              Submit essay
            </button>
          </span>
        </>
      )}

      {!clean && active && (
        <span className="w-full text-amber-600 dark:text-amber-400">
          Save your edits before submitting.
        </span>
      )}
      {error && (
        <span role="alert" data-testid="session-error" className="w-full text-red-600 dark:text-red-400">
          {error}
        </span>
      )}

      {startOpen && (
        <Dialog title="Start a writing session" onClose={() => setStartOpen(false)}>
          <div className="space-y-4">
            <fieldset>
              <legend className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Mode</legend>
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
                    <strong>Assisted learning</strong> — real-time grammar feedback and AI
                    assistance while you write.
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
                    <strong>Independent writing</strong> — no real-time assistance; AI evaluation
                    after submission.
                  </span>
                </label>
              </div>
            </fieldset>

            <label className="block text-sm">
              <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Activity</span>
              <select
                data-testid="activity-type"
                value={activity}
                onChange={(event) => setActivity(event.target.value as ActivityType)}
                className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              >
                <option value="free_writing">Free writing</option>
                <option value="practice">Practice</option>
                <option value="mock_exam">Mock exam (timed)</option>
              </select>
            </label>

            {activity === "mock_exam" && (
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Task</span>
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
                    Minutes
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
                Cancel
              </button>
              <button
                type="button"
                data-testid="confirm-start-session"
                disabled={startMutation.isPending}
                onClick={() => startMutation.mutate()}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                {startMutation.isPending ? "Starting…" : "Start session"}
              </button>
            </div>
          </div>
        </Dialog>
      )}

      {confirmSubmit && active && (
        <Dialog title="Submit this essay?" onClose={() => setConfirmSubmit(false)}>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Submitting saves an immutable final snapshot and ends the session. AI evaluation
            becomes available afterwards; your original text is never overwritten.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmSubmit(false)}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Keep writing
            </button>
            <button
              type="button"
              data-testid="confirm-submit"
              disabled={submitMutation.isPending}
              onClick={() => submitMutation.mutate(active)}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {submitMutation.isPending ? "Submitting…" : "Submit"}
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
