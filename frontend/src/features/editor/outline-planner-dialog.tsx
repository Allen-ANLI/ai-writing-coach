"use client";

/**
 * Outline planner (PRD FR-10, API Spec §14): generate a hierarchical plan
 * from the question + the learner's viewpoint, review/edit the draft, then
 * confirm. The plan never writes into the essay body; ghost-text insertion
 * stays an explicit user action in the editor.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import { ApiClientError } from "@/lib/api-client";
import {
  confirmOutline,
  generateOutline,
  getOutline,
  patchOutline,
} from "@/services/outlines";
import type { OutlineNodeData } from "@/types/api";

function buildTree(nodes: OutlineNodeData[]): OutlineNodeData[] {
  return nodes
    .filter((node) => node.parent_id === null)
    .sort((a, b) => a.sort_order - b.sort_order);
}

function childrenOf(nodes: OutlineNodeData[], parentId: string): OutlineNodeData[] {
  return nodes
    .filter((node) => node.parent_id === parentId)
    .sort((a, b) => a.sort_order - b.sort_order);
}

function NodeBranch({ nodes, parentId, depth }: { nodes: OutlineNodeData[]; parentId: string; depth: number }) {
  const children = childrenOf(nodes, parentId);
  if (children.length === 0) {
    return null;
  }
  return (
    <ul className={depth > 0 ? "ml-4 border-l border-zinc-100 pl-2 dark:border-zinc-800" : ""}>
      {children.map((node) => (
        <li key={node.id} className="mt-1">
          <p
            className={
              node.node_type === "section"
                ? "text-sm font-medium text-zinc-800 dark:text-zinc-200"
                : node.node_type === "paragraph"
                  ? "text-xs text-zinc-600 dark:text-zinc-400"
                  : "text-xs text-zinc-500 dark:text-zinc-500"
            }
          >
            {node.node_type === "sentence_idea" ? "· " : ""}
            {node.title}
          </p>
          <NodeBranch nodes={nodes} parentId={node.id} depth={depth + 1} />
        </li>
      ))}
    </ul>
  );
}

export function OutlinePlannerDialog({
  essayId,
  onClose,
  onConfirmed,
}: {
  essayId: string;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const queryClient = useQueryClient();
  const [viewpoint, setViewpoint] = useState("");
  const [outlineId, setOutlineId] = useState<string | null>(null);
  const [thesisDraft, setThesisDraft] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const outlineQuery = useQuery({
    queryKey: ["outline", outlineId],
    queryFn: async () => (await getOutline(outlineId as string)).data,
    enabled: outlineId !== null,
    refetchInterval: (query) => (query.state.data?.status === "generating" ? 1500 : false),
  });

  const errorMessage = (error: unknown, fallback: string) =>
    error instanceof ApiClientError ? error.message : fallback;

  const generate = useMutation({
    mutationFn: async () =>
      generateOutline(essayId, { viewpoint: viewpoint.trim() === "" ? null : viewpoint.trim() }),
    onSuccess: (response) => {
      setOutlineId(response.data.outline_id);
      setThesisDraft(null);
      setActionError(null);
    },
    onError: (error) => setActionError(errorMessage(error, "Could not start outline generation.")),
  });

  const saveThesis = useMutation({
    mutationFn: async () =>
      patchOutline(outlineId as string, { thesis_statement: thesisDraft ?? undefined }),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["outline", outlineId] });
    },
    onError: (error) => setActionError(errorMessage(error, "Could not save the thesis.")),
  });

  const confirm = useMutation({
    mutationFn: async () => confirmOutline(outlineId as string),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["outlines", essayId] });
      onConfirmed();
    },
    onError: (error) => setActionError(errorMessage(error, "Could not confirm the outline.")),
  });

  const outline = outlineQuery.data ?? null;

  return (
    <Dialog title="Plan your essay" onClose={onClose}>
      <div data-testid="outline-planner-dialog" className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
        <label className="block text-sm">
          <span className="text-xs font-medium text-zinc-500">Your thesis / viewpoint (optional)</span>
          <textarea
            data-testid="outline-viewpoint"
            value={viewpoint}
            onChange={(event) => setViewpoint(event.target.value)}
            maxLength={2000}
            rows={2}
            placeholder="e.g. I agree that public transport should be free in large cities."
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </label>

        <button
          type="button"
          data-testid="generate-outline"
          disabled={generate.isPending || outline?.status === "generating"}
          onClick={() => generate.mutate()}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {generate.isPending || outline?.status === "generating" ? "Planning…" : "Generate outline"}
        </button>

        {actionError && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">{actionError}</p>
        )}

        {outline?.status === "generating" && (
          <p className="text-sm text-zinc-500" data-testid="outline-generating">
            Building your plan…
          </p>
        )}
        {outline?.status === "failed" && (
          <p className="text-sm text-red-600 dark:text-red-400">
            Outline generation failed. Try again.
          </p>
        )}

        {outline && (outline.status === "draft" || outline.status === "confirmed") && (
          <section className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800" data-testid="outline-draft">
            <label className="block text-xs font-medium text-zinc-500">
              Thesis statement
              <input
                data-testid="outline-thesis"
                value={thesisDraft ?? outline.thesis_statement ?? ""}
                onChange={(event) => setThesisDraft(event.target.value)}
                disabled={outline.status !== "draft"}
                maxLength={1000}
                className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
              />
            </label>
            {outline.status === "draft" && thesisDraft !== null && (
              <button
                type="button"
                data-testid="save-thesis"
                disabled={saveThesis.isPending}
                onClick={() => saveThesis.mutate()}
                className="mt-2 rounded-md border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              >
                Save thesis
              </button>
            )}

            <div className="mt-3" data-testid="outline-tree-plan">
              <ul>
                {buildTree(outline.nodes).map((node) => (
                  <li key={node.id} className="mt-1">
                    <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{node.title}</p>
                    <NodeBranch nodes={outline.nodes} parentId={node.id} depth={1} />
                  </li>
                ))}
              </ul>
            </div>

            {outline.status === "draft" && (
              <button
                type="button"
                data-testid="confirm-outline"
                disabled={confirm.isPending}
                onClick={() => confirm.mutate()}
                className="mt-4 rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                {confirm.isPending ? "Confirming…" : "Confirm outline"}
              </button>
            )}
            {outline.status === "confirmed" && (
              <p className="mt-3 text-xs text-emerald-600 dark:text-emerald-400">
                Confirmed — the plan appears in the left outline panel.
              </p>
            )}
          </section>
        )}
      </div>
    </Dialog>
  );
}
