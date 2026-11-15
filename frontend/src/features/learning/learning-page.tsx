"use client";

/**
 * Learning Center (PRD FR-05/FR-07, API Spec §10–11): spaced-repetition
 * translation practice (Chinese prompt → English answer), summary stats and
 * the personal weakness profile. Scheduling is server-side SM-2.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dueReviews, learningSummary, submitReview, weaknesses } from "@/services/learning";
import type { ReviewPrompt, ReviewResultData } from "@/types/api";

export function LearningPage() {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<ReviewResultData | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    </main>
  );
}
