"use client";

/**
 * Study plans & tasks (PRD FR-12, ERD §13, Slice 9): plans created manually
 * or by the confirmed study-planner workflow; tasks complete with one click.
 * Review scheduling itself stays deterministic SM-2 (Slice 5B).
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createPlan, listPlans, listTasks, patchTask } from "@/services/plans";
import type { LearningTaskData } from "@/types/api";

export function PlansCard() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const plansQuery = useQuery({
    queryKey: ["learning-plans"],
    queryFn: async () => (await listPlans()).data.items,
  });
  const tasksQuery = useQuery({
    queryKey: ["learning-tasks"],
    queryFn: async () => (await listTasks()).data.items,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["learning-plans"] });
    void queryClient.invalidateQueries({ queryKey: ["learning-tasks"] });
  };

  const addPlan = useMutation({
    mutationFn: async () => createPlan({ title: title.trim() }),
    onSuccess: () => {
      setTitle("");
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not create the plan."),
  });

  const toggleTask = useMutation({
    mutationFn: async (task: LearningTaskData) =>
      patchTask(task.id, { status: task.status === "completed" ? "pending" : "completed" }),
    onMutate: async (task) => {
      await queryClient.cancelQueries({ queryKey: ["learning-tasks"] });
      const previous = queryClient.getQueryData<LearningTaskData[]>(["learning-tasks"]);
      const nextStatus = task.status === "completed" ? "pending" : "completed";
      queryClient.setQueryData<LearningTaskData[]>(["learning-tasks"], (old) =>
        old?.map((item) => (item.id === task.id ? { ...item, status: nextStatus } : item)),
      );
      return { previous };
    },
    onSuccess: () => setError(null),
    onError: (err, _task, context) => {
      setError(err instanceof Error ? err.message : "Could not update the task.");
      if (context?.previous) {
        queryClient.setQueryData(["learning-tasks"], context.previous);
      }
    },
    onSettled: () => invalidate(),
  });

  const tasks = tasksQuery.data ?? [];

  return (
    <section className="mt-8" aria-label="Study plans" data-testid="plans-card">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
        Study plans & tasks
      </h2>

      <form
        className="mt-3 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (title.trim() !== "") {
            addPlan.mutate();
          }
        }}
      >
        <label className="text-sm">
          <span className="text-xs font-medium text-zinc-500">New plan</span>
          <input
            data-testid="plan-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={255}
            placeholder="e.g. March writing sprint"
            className="mt-1 block w-64 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </label>
        <button
          type="submit"
          data-testid="create-plan"
          disabled={addPlan.isPending || title.trim() === ""}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          Add plan
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {plansQuery.data && plansQuery.data.length === 0 && (
        <p className="mt-3 text-sm text-zinc-500" data-testid="no-plans">
          No plans yet — add one above or confirm a study plan from the planner.
        </p>
      )}

      <ul className="mt-3 space-y-2" data-testid="plan-list">
        {plansQuery.data?.map((plan) => (
          <li
            key={plan.id}
            data-testid="plan-item"
            className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
          >
            <p className="font-medium text-zinc-800 dark:text-zinc-200">{plan.title}</p>
            <p className="text-xs text-zinc-500">
              {plan.status}
              {plan.goal ? ` · ${plan.goal}` : ""}
              {plan.daily_target_minutes ? ` · ${plan.daily_target_minutes} min/day` : ""}
            </p>
          </li>
        ))}
      </ul>

      {tasks.length > 0 && (
        <ul className="mt-3 space-y-2" data-testid="task-list">
          {tasks.map((task) => (
            <li
              key={task.id}
              data-testid="task-item"
              className="flex items-start gap-3 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
            >
              <input
                type="checkbox"
                data-testid="task-toggle"
                checked={task.status === "completed"}
                onChange={() => toggleTask.mutate(task)}
                className="mt-1 h-4 w-4"
                aria-label={`Mark ${task.title} ${task.status === "completed" ? "pending" : "completed"}`}
              />
              <div className="min-w-0">
                <p
                  className={`font-medium ${
                    task.status === "completed"
                      ? "text-zinc-400 line-through"
                      : "text-zinc-800 dark:text-zinc-200"
                  }`}
                >
                  [{task.task_type}] {task.title}
                </p>
                {task.description && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{task.description}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
