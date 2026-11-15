"use client";

/**
 * Personal expression knowledge base (PRD FR-04, API Spec §9).
 * Search (English/Chinese keyword), status/topic filters, manual add,
 * archive and soft delete. Semantic search arrives with the RAG slice.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import {
  archiveExpression,
  createExpression,
  deleteExpression,
  listExpressions,
} from "@/services/expressions";
import type { ExpressionData } from "@/types/api";

const STATUS_LABELS: Record<string, string> = {
  collected: "Collected",
  learning: "Learning",
  reviewing: "Reviewing",
  mastered: "Mastered",
  archived: "Archived",
};

export function KnowledgePage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [english, setEnglish] = useState("");
  const [chinese, setChinese] = useState("");
  const [topic, setTopic] = useState("");
  const [error, setError] = useState<string | null>(null);

  const expressionsQuery = useQuery({
    queryKey: ["expressions", query, statusFilter],
    queryFn: async () =>
      (
        await listExpressions({
          limit: 50,
          query: query || undefined,
          status: statusFilter || undefined,
        })
      ).data,
  });

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["expressions"] });

  const addMutation = useMutation({
    mutationFn: async () =>
      createExpression({
        english_text: english.trim(),
        chinese_meaning: chinese.trim() || null,
        topic: topic.trim() || null,
        source_type: "manual",
      }),
    onSuccess: () => {
      setAddOpen(false);
      setEnglish("");
      setChinese("");
      setTopic("");
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not save."),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => archiveExpression(id),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteExpression(id),
    onSuccess: invalidate,
  });

  const items = expressionsQuery.data?.items ?? [];

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Knowledge Base
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Your collected expressions — searchable, reviewable, yours.
          </p>
        </div>
        <button
          type="button"
          data-testid="add-expression"
          onClick={() => setAddOpen(true)}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Add expression
        </button>
      </header>

      <div className="mt-6 flex flex-wrap gap-3">
        <input
          type="search"
          data-testid="kb-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search English or Chinese…"
          className="min-w-0 flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        />
        <select
          data-testid="kb-status-filter"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        >
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {expressionsQuery.isPending && (
        <p role="status" className="mt-6 text-sm text-zinc-500">
          Loading expressions…
        </p>
      )}

      {!expressionsQuery.isPending && items.length === 0 && (
        <p data-testid="kb-empty" className="mt-6 text-sm text-zinc-500 dark:text-zinc-400">
          No expressions yet. Save suggestions from the editor, or add one manually.
        </p>
      )}

      <ul className="mt-6 space-y-3" data-testid="kb-list">
        {items.map((expression: ExpressionData) => (
          <li
            key={expression.id}
            data-testid="kb-item"
            className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  {expression.english_text}
                </p>
                {expression.chinese_meaning && (
                  <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
                    {expression.chinese_meaning}
                  </p>
                )}
                <p className="mt-1 text-xs text-zinc-400">
                  {STATUS_LABELS[expression.status] ?? expression.status}
                  {expression.topic ? ` · ${expression.topic}` : ""}
                  {expression.register ? ` · ${expression.register}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                {expression.status !== "archived" && (
                  <button
                    type="button"
                    data-testid={`kb-archive-${expression.id}`}
                    onClick={() => archiveMutation.mutate(expression.id)}
                    className="rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                  >
                    Archive
                  </button>
                )}
                <button
                  type="button"
                  data-testid={`kb-delete-${expression.id}`}
                  onClick={() => deleteMutation.mutate(expression.id)}
                  className="rounded px-2 py-1 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-950"
                >
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {addOpen && (
        <Dialog title="Add expression" onClose={() => setAddOpen(false)}>
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              addMutation.mutate();
            }}
          >
            <label className="block text-sm">
              <span className="text-xs font-medium text-zinc-500">English expression</span>
              <input
                data-testid="kb-english-input"
                required
                maxLength={2000}
                value={english}
                onChange={(event) => setEnglish(event.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              />
            </label>
            <label className="block text-sm">
              <span className="text-xs font-medium text-zinc-500">Chinese meaning (optional)</span>
              <input
                data-testid="kb-chinese-input"
                maxLength={2000}
                value={chinese}
                onChange={(event) => setChinese(event.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              />
            </label>
            <label className="block text-sm">
              <span className="text-xs font-medium text-zinc-500">Topic (optional)</span>
              <input
                data-testid="kb-topic-input"
                maxLength={80}
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              />
            </label>
            {error && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setAddOpen(false)}
                className="rounded-md px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                data-testid="kb-save"
                disabled={addMutation.isPending || english.trim() === ""}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
              >
                {addMutation.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </main>
  );
}
