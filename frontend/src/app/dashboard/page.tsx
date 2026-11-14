"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { RequireAuth } from "@/features/auth/require-auth";
import {
  CreateEssayDialog,
  DeleteEssayDialog,
  RenameEssayDialog,
  WRITING_TYPE_LABELS,
} from "@/features/essays/essay-dialogs";
import { createEssay, deleteEssay, listEssays, renameEssay } from "@/services/essays";
import type { EssayData, WritingType } from "@/types/api";

type DialogState =
  | { kind: "create" }
  | { kind: "rename"; essay: EssayData }
  | { kind: "delete"; essay: EssayData }
  | null;

function DashboardContent() {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<DialogState>(null);

  const essaysQuery = useQuery({
    queryKey: ["essays"],
    queryFn: async () => (await listEssays()).data,
  });

  const invalidateEssays = () => queryClient.invalidateQueries({ queryKey: ["essays"] });

  const createMutation = useMutation({
    mutationFn: (payload: { title: string | null; writing_type: WritingType }) =>
      createEssay(payload),
    onSuccess: async () => {
      await invalidateEssays();
      setDialog(null);
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ essayId, title }: { essayId: string; title: string | null }) =>
      renameEssay(essayId, title),
    onSuccess: async () => {
      await invalidateEssays();
      setDialog(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (essayId: string) => deleteEssay(essayId),
    onSuccess: async () => {
      await invalidateEssays();
      setDialog(null);
    },
  });

  const items = essaysQuery.data?.items;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Your essays
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Create an essay to start writing. The editor arrives in a later stage.
          </p>
        </div>
        <button
          type="button"
          data-testid="new-essay"
          onClick={() => setDialog({ kind: "create" })}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          New essay
        </button>
      </header>

      <section aria-label="Essay list" className="mt-8">
        {essaysQuery.isPending && (
          <p role="status" data-testid="essays-loading" className="text-sm text-zinc-500 dark:text-zinc-400">
            Loading your essays…
          </p>
        )}

        {essaysQuery.isError && (
          <div
            role="alert"
            data-testid="essays-error"
            className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
          >
            <p>Could not load your essays.</p>
            <button
              type="button"
              onClick={() => void essaysQuery.refetch()}
              className="mt-2 rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium hover:bg-red-100 dark:border-red-800 dark:hover:bg-red-900"
            >
              Retry
            </button>
          </div>
        )}

        {items && items.length === 0 && (
          <div
            data-testid="essays-empty"
            className="rounded-xl border border-dashed border-zinc-300 p-10 text-center dark:border-zinc-700"
          >
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">No essays yet</p>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Create your first essay to get started.
            </p>
          </div>
        )}

        {items && items.length > 0 && (
          <ul className="space-y-3" data-testid="essay-list">
            {items.map((essay) => (
              <li
                key={essay.id}
                data-testid="essay-item"
                className="flex items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
              >
                <Link href={`/essays/${essay.id}`} className="min-w-0 flex-1">
                  <p
                    data-testid="essay-title"
                    className="truncate font-medium text-zinc-900 hover:underline dark:text-zinc-100"
                  >
                    {essay.title ?? "Untitled"}
                  </p>
                  <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                    {WRITING_TYPE_LABELS[essay.writing_type]} · Updated{" "}
                    {new Date(essay.updated_at).toLocaleString()}
                  </p>
                </Link>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    data-testid="rename-essay"
                    onClick={() => setDialog({ kind: "rename", essay })}
                    className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    data-testid="delete-essay"
                    onClick={() => setDialog({ kind: "delete", essay })}
                    className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {dialog?.kind === "create" && (
        <CreateEssayDialog
          onClose={() => setDialog(null)}
          onCreate={(payload) => createMutation.mutateAsync(payload)}
        />
      )}
      {dialog?.kind === "rename" && (
        <RenameEssayDialog
          essay={dialog.essay}
          onClose={() => setDialog(null)}
          onRename={(title) =>
            renameMutation.mutateAsync({ essayId: dialog.essay.id, title })
          }
        />
      )}
      {dialog?.kind === "delete" && (
        <DeleteEssayDialog
          essay={dialog.essay}
          onClose={() => setDialog(null)}
          onConfirm={() => deleteMutation.mutateAsync(dialog.essay.id)}
        />
      )}
    </main>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
