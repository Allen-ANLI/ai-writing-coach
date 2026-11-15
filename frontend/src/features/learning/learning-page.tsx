"use client";

/**
 * Learning Center (PRD FR-05/FR-07, API Spec §10–11): spaced-repetition
 * translation practice (Chinese prompt → English answer), summary stats and
 * the personal weakness profile. Scheduling is server-side SM-2.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dueReviews, learningSummary, submitReview, weaknesses } from "@/services/learning";
import { createWorkflow, getWorkflow, resumeWorkflow } from "@/services/workflows";
import type { ReviewPrompt, ReviewResultData, StudyPlanResult } from "@/types/api";
import { PlansCard } from "@/features/learning/plans-card";

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
    onError: (err) => setPlannerError(err instanceof Error ? err.message : "Could not start planner."),
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
    onError: (err) => setPlannerError(err instanceof Error ? err.message : "Action failed."),
  });

  const planner = plannerQuery.data ?? null;
  const studyPlan = (planner?.result_json?.plan ?? null) as StudyPlanResult | null;

  const current: ReviewPrompt | null = dueQuery.data?.items[0] ?? null;

  const reviewMutation = useMutation({
    mutationFn: async () => {
      if (!current) {
        throw new Error("No review available.");
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
    onError: (err) => setError(err instanceof Error ? err.message : "Review failed."),
  });

  const nextReview = () => {
    setResult(null);
    void queryClient.invalidateQueries({ queryKey: ["learning-due"] });
  };

  const summary = summaryQuery.data;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Learning Center
      </h1>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
        Translate from Chinese; any natural correct English is accepted. Spaced repetition
        schedules your reviews.
      </p>

      {summary && (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="learning-summary">
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Expressions</p>
            <p className="text-xl font-semibold">{summary.total_expressions}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Due now</p>
            <p className="text-xl font-semibold" data-testid="due-count">{summary.due_now}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Mastered</p>
            <p className="text-xl font-semibold">{summary.mastered}</p>
          </div>
          <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="text-xs text-zinc-500">Reviewed today</p>
            <p className="text-xl font-semibold">{summary.reviewed_today}</p>
          </div>
        </div>
      )}

      <section className="mt-8" aria-label="Translation practice">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Practice
        </h2>

        {dueQuery.isPending && <p className="mt-3 text-sm text-zinc-500">Loading reviews…</p>}

        {!dueQuery.isPending && !current && !result && (
          <p data-testid="no-reviews" className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
            Nothing due right now. Collect expressions from the editor or knowledge base.
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
              {current.topic ?? "General"} · review #{current.review_count + 1}
            </p>
            <p className="mt-2 text-lg font-medium text-zinc-900 dark:text-zinc-100" data-testid="review-prompt">
              {current.chinese_meaning ?? current.usage_context ?? "Translate this expression"}
            </p>
            <label className="mt-3 block text-sm">
              <span className="text-xs font-medium text-zinc-500">Your English translation</span>
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
              {reviewMutation.isPending ? "Checking…" : "Check answer"}
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
              {result.is_correct ? "Correct — well done." : "Not quite."}
            </p>
            <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
              Reference: <strong>{result.reference_expression}</strong>
            </p>
            {result.feedback && (
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{result.feedback}</p>
            )}
            <p className="mt-1 text-xs text-zinc-400">
              Next review in {result.interval_days} day(s) · streak {result.streak_count}
            </p>
            <button
              type="button"
              data-testid="review-next"
              onClick={nextReview}
              className="mt-3 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
            >
              Next review
            </button>
          </div>
        )}
      </section>

      <section className="mt-8" aria-label="Weakness profile">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Your recurring weaknesses
        </h2>
        {weaknessQuery.data && weaknessQuery.data.length === 0 && (
          <p className="mt-3 text-sm text-zinc-500">
            No recurring weaknesses detected yet — keep writing.
          </p>
        )}
        <ul className="mt-3 space-y-2" data-testid="weakness-list">
          {weaknessQuery.data?.map((weakness) => (
            <li
              key={`${weakness.category}-${weakness.sub_category}`}
              className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
            >
              <span className="font-medium text-zinc-800 dark:text-zinc-200">
                {weakness.category}
                {weakness.sub_category ? ` · ${weakness.sub_category}` : ""}
              </span>
              <span className="text-xs text-zinc-500">
                {weakness.total_occurrences} occurrence{weakness.total_occurrences === 1 ? "" : "s"}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <PlansCard />

      <section className="mt-8" aria-label="Study planner" data-testid="study-planner">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Personalized study planner
        </h2>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          An AI workflow combines your weakness profile and mastery status into study
          suggestions. Nothing is saved until you confirm.
        </p>

        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="text-xs font-medium text-zinc-500">Goal (optional)</span>
            <input
              data-testid="planner-goal"
              value={plannerGoal}
              onChange={(event) => setPlannerGoal(event.target.value)}
              maxLength={200}
              placeholder="e.g. Reach band 7 in three months"
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
            {startPlanner.isPending || planner?.status === "running" ? "Planning…" : "Generate study plan"}
          </button>
        </div>

        {plannerError && (
          <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{plannerError}</p>
        )}

        {planner && (
          <p className="mt-2 text-xs text-zinc-400" data-testid="plan-status">
            Status: {planner.status}
            {planner.current_step ? ` · step: ${planner.current_step}` : ""}
          </p>
        )}
        {planner?.status === "failed" && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">{planner.error_message}</p>
        )}

        {planner?.status === "awaiting_confirmation" && studyPlan && (
          <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
            <p className="text-xs font-medium text-zinc-500">
              Focus: {studyPlan.focus_areas.join(", ")}
            </p>
            <ul className="mt-2 space-y-2" data-testid="plan-suggestions">
              {studyPlan.suggestions.map((suggestion, index) => (
                <li key={`${suggestion.title}-${index}`} className="text-sm">
                  <p className="font-medium text-zinc-800 dark:text-zinc-200">
                    [{suggestion.task_type}] {suggestion.title}
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
                Confirm plan
              </button>
              <button
                type="button"
                data-testid="reject-plan"
                disabled={resumePlanner.isPending}
                onClick={() => resumePlanner.mutate("reject")}
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {planner?.status === "completed" && (
          <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400" data-testid="plan-done">
            {planner.result_json?.outcome &&
            (planner.result_json.outcome as Record<string, unknown>).rejected
              ? "Plan rejected."
              : "Plan confirmed — follow the suggestions in your practice."}
          </p>
        )}
      </section>
    </main>
  );
}
