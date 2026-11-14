"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { WRITING_TYPE_LABELS } from "@/features/essays/essay-dialogs";
import { getEssay } from "@/services/essays";

/** Reads the dynamic route param; must render inside <Suspense> (Next 16). */
export function EssayDetailRoute() {
  const params = useParams<{ id: string }>();
  return <EssayDetail essayId={params.id} />;
}

export function EssayDetail({ essayId }: { essayId: string }) {
  const essayQuery = useQuery({
    queryKey: ["essay", essayId],
    queryFn: async () => (await getEssay(essayId)).data,
  });

  const essay = essayQuery.data;

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12">
      <Link
        href="/dashboard"
        className="text-sm font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
      >
        ← Back to essays
      </Link>

      {essayQuery.isPending && (
        <p role="status" className="mt-6 text-sm text-zinc-500 dark:text-zinc-400">
          Loading essay…
        </p>
      )}

      {essayQuery.isError && (
        <p role="alert" data-testid="essay-detail-error" className="mt-6 text-sm text-red-600 dark:text-red-400">
          This essay could not be loaded. It may have been deleted.
        </p>
      )}

      {essay && (
        <article className="mt-6 space-y-6">
          <header>
            <h1
              data-testid="essay-detail-title"
              className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
            >
              {essay.title ?? "Untitled"}
            </h1>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              {WRITING_TYPE_LABELS[essay.writing_type]} · {essay.status}
            </p>
          </header>

          <section
            aria-label="Essay details"
            className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
          >
            <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-zinc-500 dark:text-zinc-400">Created</dt>
                <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                  {new Date(essay.created_at).toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500 dark:text-zinc-400">Last updated</dt>
                <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                  {new Date(essay.updated_at).toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500 dark:text-zinc-400">Word count</dt>
                <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                  {essay.working_document.word_count}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500 dark:text-zinc-400">Document revision</dt>
                <dd className="font-medium text-zinc-900 dark:text-zinc-100">
                  {essay.working_document.server_revision}
                </dd>
              </div>
            </dl>
            <p className="mt-4 text-xs text-zinc-400 dark:text-zinc-500">
              The writing editor is not part of this stage yet.
            </p>
          </section>
        </article>
      )}
    </main>
  );
}
