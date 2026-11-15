"use client";

/**
 * Version history drawer: list immutable snapshots, view content, create
 * checkpoints, restore with confirmation. Restore and checkpoint require a
 * clean save state so base_revision/source_revision are exact.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import { ExtractionDialog } from "@/features/editor/extraction-dialog";
import { ApiClientError } from "@/lib/api-client";
import { createSnapshot, getVersion, listVersions, restoreVersion } from "@/services/documents";
import type { TipTapDocument, VersionData, VersionDetailData } from "@/types/api";
import type { SaveStatus } from "@/features/editor/use-autosave";

const VERSION_TYPE_LABELS: Record<string, string> = {
  original: "Original",
  checkpoint: "Checkpoint",
  assisted: "Assisted",
  final: "Final",
  ai_rewrite: "AI rewrite",
};

export function VersionHistory({
  essayId,
  serverRevision,
  saveStatus,
  onClose,
  onRestored,
}: {
  essayId: string;
  serverRevision: number;
  saveStatus: SaveStatus;
  onClose: () => void;
  onRestored: (content: TipTapDocument, revision: number) => void;
}) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [viewing, setViewing] = useState<VersionDetailData | null>(null);
  const [confirming, setConfirming] = useState<VersionData | null>(null);
  const [extractingVersionId, setExtractingVersionId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const versionsQuery = useQuery({
    queryKey: ["versions", essayId],
    queryFn: async () => (await listVersions(essayId)).data,
  });

  const checkpointMutation = useMutation({
    mutationFn: async () => {
      const trimmed = label.trim();
      return createSnapshot(
        essayId,
        {
          source_revision: serverRevision,
          version_type: "checkpoint",
          label: trimmed === "" ? null : trimmed,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: () => {
      setLabel("");
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["versions", essayId] });
    },
    onError: (error) => {
      setActionError(
        error instanceof ApiClientError ? error.message : "Could not create the checkpoint.",
      );
    },
  });

  const viewMutation = useMutation({
    mutationFn: async (versionId: string) => (await getVersion(essayId, versionId)).data,
    onSuccess: (data) => setViewing(data),
    onError: () => setActionError("Could not load this version."),
  });

  const restoreMutation = useMutation({
    mutationFn: async (version: VersionData) => {
      const detail = (await getVersion(essayId, version.id)).data;
      const response = await restoreVersion(essayId, {
        version_id: version.id,
        base_revision: serverRevision,
      });
      return { detail, response };
    },
    onSuccess: ({ detail, response }) => {
      setConfirming(null);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["versions", essayId] });
      void queryClient.invalidateQueries({ queryKey: ["essay", essayId] });
      onRestored(detail.content_json, response.data.server_revision);
    },
    onError: (error) => {
      setConfirming(null);
      setActionError(
        error instanceof ApiClientError && error.status === 409
          ? "The document changed since you opened history. Close history, save, and try again."
          : "Could not restore this version.",
      );
    },
  });

  const clean = saveStatus === "saved";

  return (
    <Dialog title="Version history" onClose={onClose}>
      <div className="space-y-4">
        <section aria-label="Create checkpoint" className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <label htmlFor="checkpoint-label" className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
            Save a checkpoint of the current text
          </label>
          <div className="mt-2 flex gap-2">
            <input
              id="checkpoint-label"
              type="text"
              value={label}
              maxLength={255}
              placeholder="Optional label"
              onChange={(event) => setLabel(event.target.value)}
              className="min-w-0 flex-1 rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
            <button
              type="button"
              data-testid="create-checkpoint"
              disabled={!clean || checkpointMutation.isPending}
              onClick={() => checkpointMutation.mutate()}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {checkpointMutation.isPending ? "Saving…" : "Checkpoint"}
            </button>
          </div>
          {!clean && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              Save your edits first — checkpoints capture the saved revision.
            </p>
          )}
        </section>

        {actionError && (
          <p role="alert" data-testid="history-error" className="text-sm text-red-600 dark:text-red-400">
            {actionError}
          </p>
        )}

        {versionsQuery.isPending && <p className="text-sm text-zinc-500">Loading versions…</p>}
        {versionsQuery.isError && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            Could not load version history.
          </p>
        )}

        <ul className="max-h-72 space-y-2 overflow-y-auto" data-testid="version-list">
          {versionsQuery.data?.items.map((version) => (
            <li
              key={version.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  v{version.version_no} · {VERSION_TYPE_LABELS[version.version_type] ?? version.version_type}
                  {version.label ? ` — ${version.label}` : ""}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {version.word_count} words · {new Date(version.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <button
                  type="button"
                  onClick={() => viewMutation.mutate(version.id)}
                  className="rounded px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  View
                </button>
                <button
                  type="button"
                  data-testid={`extract-${version.version_no}`}
                  onClick={() => setExtractingVersionId(version.id)}
                  className="rounded px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  Extract
                </button>
                <button
                  type="button"
                  data-testid={`restore-${version.version_no}`}
                  disabled={!clean || restoreMutation.isPending}
                  onClick={() => setConfirming(version)}
                  className="rounded px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  Restore
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {viewing && (
        <Dialog title={`Version ${viewing.version_no} (read-only)`} onClose={() => setViewing(null)}>
          <pre
            data-testid="version-content"
            className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-3 text-sm text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
          >
            {viewing.plain_text || "(empty)"}
          </pre>
        </Dialog>
      )}

      {confirming && (
        <Dialog title="Restore this version?" onClose={() => setConfirming(null)}>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Version {confirming.version_no} will replace your current working text. The version
            itself stays unchanged, and your current text remains in history if you checkpointed it.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="button"
              data-testid="confirm-restore"
              onClick={() => restoreMutation.mutate(confirming)}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              Restore
            </button>
          </div>
        </Dialog>
      )}

      {extractingVersionId && (
        <ExtractionDialog
          essayId={essayId}
          versionId={extractingVersionId}
          onClose={() => setExtractingVersionId(null)}
        />
      )}
    </Dialog>
  );
}
