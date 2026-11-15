"use client";

/**
 * Expression extraction with user confirmation (PRD FR-04.5, API Spec §9).
 * Candidates come from an immutable version; NOTHING is saved until the user
 * selects and confirms. Saving uses the knowledge-base create endpoint with
 * source_type=essay.
 */

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Dialog } from "@/components/dialog";
import { createExpression, extractExpressions } from "@/services/expressions";
import type { ExtractionCandidate } from "@/types/api";

export function ExtractionDialog({
  essayId,
  versionId,
  onClose,
}: {
  essayId: string;
  versionId: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [candidates, setCandidates] = useState<ExtractionCandidate[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedCount, setSavedCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    extractExpressions(essayId, { version_id: versionId, extraction_scope: "full" })
      .then((response) => {
        if (!cancelled) {
          setCandidates(response.data.candidates);
          setSelected(new Set(response.data.candidates.map((_, index) => index)));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("表达提取暂时不可用，请稍后重试。");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [essayId, versionId]);

  const toggle = (index: number) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const saveSelected = async () => {
    if (!candidates) {
      return;
    }
    setSaving(true);
    setError(null);
    let saved = 0;
    for (const index of Array.from(selected).sort((a, b) => a - b)) {
      const candidate = candidates[index];
      try {
        await createExpression({
          english_text: candidate.english_text,
          chinese_meaning: candidate.chinese_meaning,
          original_text: candidate.original_text,
          learning_value_reason: candidate.learning_value_reason,
          usage_context: candidate.usage_context,
          topic: candidate.topic,
          grammar_pattern: candidate.grammar_pattern,
          source_type: "essay",
          essay_id: essayId,
        });
        saved += 1;
      } catch {
        // Duplicates are skipped; keep saving the rest.
      }
    }
    setSaving(false);
    setSavedCount(saved);
    void queryClient.invalidateQueries({ queryKey: ["expressions"] });
  };

  return (
    <Dialog title="提取表达" onClose={onClose}>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {!candidates && !error && (
        <p role="status" className="text-sm text-zinc-500">
          正在分析该版本中值得学习的表达…
        </p>
      )}

      {candidates && candidates.length === 0 && (
        <p className="text-sm text-zinc-500">该版本没有可提取的表达。</p>
      )}

      {savedCount !== null ? (
        <div data-testid="extraction-saved">
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            已将 {savedCount} 条表达保存到知识库。
          </p>
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
            >
              完成
            </button>
          </div>
        </div>
      ) : (
        candidates &&
        candidates.length > 0 && (
          <div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              保存前请确认 — 勾选你想保留的表达。
            </p>
            <ul className="awc-scroll mt-3 max-h-72 space-y-2 overflow-y-auto" data-testid="extraction-candidates">
              {candidates.map((candidate, index) => (
                <li key={index}>
                  <label className="flex cursor-pointer items-start gap-2 rounded-md border border-zinc-200 p-2 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800">
                    <input
                      type="checkbox"
                      checked={selected.has(index)}
                      onChange={() => toggle(index)}
                      className="mt-1"
                      data-testid={`extraction-select-${index}`}
                    />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-zinc-900 dark:text-zinc-100">
                        {candidate.english_text}
                      </span>
                      <span className="block text-xs text-zinc-500 dark:text-zinc-400">
                        {candidate.chinese_meaning}
                      </span>
                      <span className="block text-xs text-zinc-400 dark:text-zinc-500">
                        {candidate.learning_value_reason}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                取消
              </button>
              <button
                type="button"
                data-testid="extraction-save"
                disabled={saving || selected.size === 0}
                onClick={() => void saveSelected()}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
              >
                {saving ? "保存中…" : `保存所选（${selected.size}）`}
              </button>
            </div>
          </div>
        )
      )}
    </Dialog>
  );
}
