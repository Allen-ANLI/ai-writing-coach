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
          setError("Extraction is unavailable right now.");
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
    <Dialog title="Extract expressions" onClose={onClose}>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      {!candidates && !error && (
        <p role="status" className="text-sm text-zinc-500">
          Analyzing this version for expressions worth learning…
        </p>
      )}

      {candidates && candidates.length === 0 && (
        <p className="text-sm text-zinc-500">No extraction candidates found in this version.</p>
      )}

      {savedCount !== null ? (
        <div data-testid="extraction-saved">
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            Saved {savedCount} expression{savedCount === 1 ? "" : "s"} to your knowledge base.
          </p>
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
            >
              Done
            </button>
          </div>
        </div>
      ) : (
        candidates &&
        candidates.length > 0 && (
          <div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Confirm before saving — select the expressions you want to keep.
            </p>
            <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto" data-testid="extraction-candidates">
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
                Cancel
              </button>
              <button
                type="button"
                data-testid="extraction-save"
                disabled={saving || selected.size === 0}
                onClick={() => void saveSelected()}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
              >
                {saving ? "Saving…" : `Save selected (${selected.size})`}
              </button>
            </div>
          </div>
        )
      )}
    </Dialog>
  );
}
