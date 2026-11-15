"use client";

/**
 * 历史版本抽屉：列出不可变快照、查看内容、创建存档点、确认后恢复。
 * 恢复与存档要求干净的保存状态，保证 base_revision/source_revision 精确。
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
  original: "原始版本",
  checkpoint: "存档点",
  assisted: "辅助写作",
  final: "最终提交",
  ai_rewrite: "AI 改写",
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
        error instanceof ApiClientError ? error.message : "无法创建存档点。",
      );
    },
  });

  const viewMutation = useMutation({
    mutationFn: async (versionId: string) => (await getVersion(essayId, versionId)).data,
    onSuccess: (data) => setViewing(data),
    onError: () => setActionError("无法加载该版本。"),
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
          ? "打开历史后文档发生了变化。请关闭历史、保存后再试。"
          : "无法恢复该版本。",
      );
    },
  });

  const clean = saveStatus === "saved";

  return (
    <Dialog title="历史版本" onClose={onClose}>
      <div className="space-y-4">
        <section aria-label="创建存档点" className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <label htmlFor="checkpoint-label" className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
            为当前文本创建存档点
          </label>
          <div className="mt-2 flex gap-2">
            <input
              id="checkpoint-label"
              type="text"
              value={label}
              maxLength={255}
              placeholder="备注（可选）"
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
              {checkpointMutation.isPending ? "保存中…" : "创建存档点"}
            </button>
          </div>
          {!clean && (
            <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
              请先保存修改 — 存档点捕获的是已保存的修订。
            </p>
          )}
        </section>

        {actionError && (
          <p role="alert" data-testid="history-error" className="text-sm text-red-600 dark:text-red-400">
            {actionError}
          </p>
        )}

        {versionsQuery.isPending && <p className="text-sm text-zinc-500">版本加载中…</p>}
        {versionsQuery.isError && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            无法加载历史版本。
          </p>
        )}

        <ul className="awc-scroll max-h-72 space-y-2 overflow-y-auto" data-testid="version-list">
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
                  {version.word_count} 词 · {new Date(version.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <button
                  type="button"
                  onClick={() => viewMutation.mutate(version.id)}
                  className="rounded px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  查看
                </button>
                <button
                  type="button"
                  data-testid={`extract-${version.version_no}`}
                  onClick={() => setExtractingVersionId(version.id)}
                  className="rounded px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  提取表达
                </button>
                <button
                  type="button"
                  data-testid={`restore-${version.version_no}`}
                  disabled={!clean || restoreMutation.isPending}
                  onClick={() => setConfirming(version)}
                  className="rounded px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  恢复
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {viewing && (
        <Dialog title={`版本 ${viewing.version_no}（只读）`} onClose={() => setViewing(null)}>
          <pre
            data-testid="version-content"
            className="awc-scroll max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-zinc-50 p-3 text-sm text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
          >
            {viewing.plain_text || "（空）"}
          </pre>
        </Dialog>
      )}

      {confirming && (
        <Dialog title="恢复该版本？" onClose={() => setConfirming(null)}>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            版本 {confirming.version_no} 将替换当前工作文本。版本本身保持不变；
            如果当前文本已创建存档点，仍可在历史中找回。
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              取消
            </button>
            <button
              type="button"
              data-testid="confirm-restore"
              onClick={() => restoreMutation.mutate(confirming)}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              恢复
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
