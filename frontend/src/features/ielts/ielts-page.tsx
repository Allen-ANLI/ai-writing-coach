"use client";

/**
 * IELTS Practice (PRD FR-08, API Spec §12): browse the original question
 * bank, filter by task/topic/type, favorite questions, and start a writing
 * session bound to the selected question. Evaluation stays a post-writing
 * action (ADR-016) — this page only creates the essay.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createEssay } from "@/services/essays";
import {
  favoriteIeltsQuestion,
  getIeltsQuestion,
  listIeltsQuestions,
  listIeltsTags,
  randomIeltsQuestion,
  unfavoriteIeltsQuestion,
} from "@/services/ielts";
import type { IeltsQuestionDetail, IeltsQuestionSummary } from "@/types/api";

const QUESTION_TYPE_LABELS: Record<string, string> = {
  line_graph: "Line graph",
  bar_chart: "Bar chart",
  pie_chart: "Pie chart",
  table: "Table",
  process: "Process",
  map: "Map",
  letter_formal: "Formal letter",
  letter_semi_formal: "Semi-formal letter",
  letter_informal: "Informal letter",
  opinion: "Opinion",
  discussion: "Discussion",
  advantages_disadvantages: "Advantages / disadvantages",
  problem_solution: "Problem / solution",
  two_part: "Two-part question",
};

const TASK1_TYPES = [
  "line_graph",
  "bar_chart",
  "pie_chart",
  "table",
  "process",
  "map",
  "letter_formal",
  "letter_semi_formal",
  "letter_informal",
];
const TASK2_TYPES = [
  "opinion",
  "discussion",
  "advantages_disadvantages",
  "problem_solution",
  "two_part",
];

function typeLabel(questionType: string | null): string {
  if (!questionType) return "Question";
  return QUESTION_TYPE_LABELS[questionType] ?? questionType;
}

function taskLabel(taskType: string): string {
  return taskType === "task1" ? "Task 1" : "Task 2";
}

export function IeltsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [taskType, setTaskType] = useState("");
  const [topic, setTopic] = useState("");
  const [questionType, setQuestionType] = useState("");
  const [selected, setSelected] = useState<IeltsQuestionDetail | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const tagsQuery = useQuery({
    queryKey: ["ielts-tags"],
    queryFn: async () => (await listIeltsTags()).data.items,
  });

  const questionsQuery = useInfiniteQuery({
    queryKey: ["ielts-questions", taskType, topic, questionType],
    queryFn: async ({ pageParam }) =>
      (
        await listIeltsQuestions({
          limit: 12,
          cursor: pageParam ?? undefined,
          task_type: taskType || undefined,
          topic: topic || undefined,
          question_type: questionType || undefined,
        })
      ).data,
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  });

  const favoriteMutation = useMutation({
    mutationFn: async (question: IeltsQuestionSummary) => {
      if (question.is_favorited) {
        await unfavoriteIeltsQuestion(question.id);
      } else {
        await favoriteIeltsQuestion(question.id);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ielts-questions"] });
      if (selected) {
        setSelected({ ...selected, is_favorited: !selected.is_favorited });
      }
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Favorite failed."),
  });

  const randomMutation = useMutation({
    mutationFn: async () => (await randomIeltsQuestion()).data,
    onSuccess: (question) => {
      setSelected(question);
      setActionError(null);
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "No question available."),
  });

  const startWritingMutation = useMutation({
    mutationFn: async (question: IeltsQuestionDetail) =>
      (
        await createEssay({
          title: `IELTS ${taskLabel(question.task_type)} — ${typeLabel(question.question_type)}`,
          writing_type: question.task_type === "task1" ? "ielts_task1" : "ielts_task2",
          question_id: question.id,
        })
      ).data,
    onSuccess: (essay) => {
      router.push(`/essays/${essay.id}`);
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Could not start writing."),
  });

  const items = questionsQuery.data?.pages.flatMap((page) => page.items) ?? [];
  const typeOptions = taskType === "task1" ? TASK1_TYPES : taskType === "task2" ? TASK2_TYPES : [...TASK1_TYPES, ...TASK2_TYPES];

  const favoriteButton = (question: IeltsQuestionSummary, testId: string) => (
    <button
      type="button"
      data-testid={testId}
      aria-pressed={question.is_favorited}
      onClick={() => favoriteMutation.mutate(question)}
      className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
        question.is_favorited
          ? "border-amber-400 bg-amber-50 text-amber-700 dark:border-amber-500 dark:bg-amber-950 dark:text-amber-300"
          : "border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
      }`}
    >
      {question.is_favorited ? "★ Favorited" : "☆ Favorite"}
    </button>
  );

  if (selected) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10" data-testid="ielts-page">
        <button
          type="button"
          data-testid="back-to-list"
          onClick={() => setSelected(null)}
          className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
        >
          ← Back to question bank
        </button>

        <div className="mt-4 rounded-lg border border-zinc-200 p-5 dark:border-zinc-800" data-testid="question-detail">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-zinc-900 px-2.5 py-1 font-medium text-white dark:bg-zinc-100 dark:text-zinc-900">
              {taskLabel(selected.task_type)}
            </span>
            <span className="rounded-full border border-zinc-300 px-2.5 py-1 text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
              {typeLabel(selected.question_type)}
            </span>
            {selected.difficulty && (
              <span className="rounded-full border border-zinc-300 px-2.5 py-1 capitalize text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
                {selected.difficulty}
              </span>
            )}
          </div>

          <p className="mt-4 whitespace-pre-line text-sm leading-relaxed text-zinc-800 dark:text-zinc-200" data-testid="detail-prompt">
            {selected.prompt_text}
          </p>

          {selected.prompt_translation && (
            <div className="mt-4 rounded-md bg-zinc-50 p-3 dark:bg-zinc-900">
              <p className="text-xs font-medium text-zinc-400">中文翻译</p>
              <p className="mt-1 whitespace-pre-line text-sm text-zinc-600 dark:text-zinc-300" data-testid="detail-translation">
                {selected.prompt_translation}
              </p>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-1.5">
            {selected.tags.map((tag) => (
              <span key={tag.id} className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                {tag.name}
              </span>
            ))}
          </div>

          <p className="mt-4 text-xs text-zinc-400">
            {selected.source_title ?? "Original practice question"} · license: {selected.license_status}
          </p>

          {actionError && (
            <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">{actionError}</p>
          )}

          <div className="mt-5 flex items-center gap-3">
            <button
              type="button"
              data-testid="start-writing"
              disabled={startWritingMutation.isPending}
              onClick={() => startWritingMutation.mutate(selected)}
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {startWritingMutation.isPending ? "Creating essay…" : "Start writing"}
            </button>
            {favoriteButton(selected, "favorite-toggle")}
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10" data-testid="ielts-page">
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        IELTS Practice
      </h1>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
        Original practice questions covering every Task 1 and Task 2 type. Pick a question,
        then write — grammar help and evaluation follow the finalized editor flow.
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="text-xs font-medium text-zinc-500">Task</span>
          <select
            data-testid="filter-task-type"
            value={taskType}
            onChange={(event) => {
              setTaskType(event.target.value);
              setQuestionType("");
            }}
            className="mt-1 block rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="">All tasks</option>
            <option value="task1">Task 1</option>
            <option value="task2">Task 2</option>
          </select>
        </label>

        <label className="text-sm">
          <span className="text-xs font-medium text-zinc-500">Topic</span>
          <select
            data-testid="filter-topic"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            className="mt-1 block rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="">All topics</option>
            {tagsQuery.data?.map((tag) => (
              <option key={tag.id} value={tag.slug}>
                {tag.name} ({tag.question_count})
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="text-xs font-medium text-zinc-500">Question type</span>
          <select
            data-testid="filter-question-type"
            value={questionType}
            onChange={(event) => setQuestionType(event.target.value)}
            className="mt-1 block rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="">All types</option>
            {typeOptions.map((value) => (
              <option key={value} value={value}>
                {typeLabel(value)}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          data-testid="random-question"
          disabled={randomMutation.isPending}
          onClick={() => randomMutation.mutate()}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          {randomMutation.isPending ? "Picking…" : "Random question"}
        </button>
      </div>

      {actionError && (
        <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">{actionError}</p>
      )}

      {questionsQuery.isPending && (
        <p className="mt-6 text-sm text-zinc-500">Loading questions…</p>
      )}

      {!questionsQuery.isPending && items.length === 0 && (
        <p data-testid="ielts-empty" className="mt-6 text-sm text-zinc-500 dark:text-zinc-400">
          No questions match these filters. Try a different combination.
        </p>
      )}

      <ul className="mt-6 space-y-3" data-testid="question-list">
        {items.map((question) => (
          <li
            key={question.id}
            data-testid="question-card"
            className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
          >
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full bg-zinc-900 px-2.5 py-1 font-medium text-white dark:bg-zinc-100 dark:text-zinc-900">
                {taskLabel(question.task_type)}
              </span>
              <span className="rounded-full border border-zinc-300 px-2.5 py-1 text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
                {typeLabel(question.question_type)}
              </span>
              {question.difficulty && (
                <span className="rounded-full border border-zinc-300 px-2.5 py-1 capitalize text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
                  {question.difficulty}
                </span>
              )}
              <span className="ml-auto flex gap-1.5">
                {question.tags.slice(0, 3).map((tag) => (
                  <span key={tag.id} className="rounded-full bg-zinc-100 px-2 py-1 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                    {tag.name}
                  </span>
                ))}
              </span>
            </div>
            <p className="mt-3 line-clamp-3 whitespace-pre-line text-sm text-zinc-700 dark:text-zinc-300">
              {question.prompt_text}
            </p>
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                data-testid="view-question"
                onClick={() => {
                  void getIeltsQuestion(question.id)
                    .then((response) => {
                      setSelected(response.data);
                      setActionError(null);
                    })
                    .catch((err: unknown) =>
                      setActionError(err instanceof Error ? err.message : "Could not load question."),
                    );
                }}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                View question
              </button>
              {favoriteButton(question, "favorite-toggle")}
            </div>
          </li>
        ))}
      </ul>

      {questionsQuery.hasNextPage && (
        <button
          type="button"
          data-testid="load-more"
          disabled={questionsQuery.isFetchingNextPage}
          onClick={() => questionsQuery.fetchNextPage()}
          className="mt-6 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          {questionsQuery.isFetchingNextPage ? "Loading…" : "Load more"}
        </button>
      )}
    </main>
  );
}
