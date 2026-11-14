"use client";

/**
 * Floating contextual teaching card (PRD FR-02.4, SD §5.5). Opens near the
 * error; content is generated for the user's CURRENT sentence — never a
 * generic template. Viewing the answer is not accepting it.
 */

import { useEffect } from "react";

import type { TeachingState } from "@/features/editor/grammar/use-grammar";

export function TeachingCard({
  teaching,
  onClose,
}: {
  teaching: TeachingState;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-label="Detailed teaching"
      data-testid="teaching-card"
      className="fixed z-50 w-96 max-w-[calc(100vw-2rem)] rounded-xl border border-zinc-200 bg-white p-4 shadow-xl dark:border-zinc-700 dark:bg-zinc-900"
      style={{ top: teaching.top, left: teaching.left }}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          {teaching.loading ? "Preparing teaching…" : (teaching.data?.title ?? "Teaching")}
        </h3>
        <button
          type="button"
          aria-label="Close teaching"
          data-testid="close-teaching"
          onClick={onClose}
          className="rounded px-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        >
          ×
        </button>
      </div>

      {teaching.loading && (
        <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
          Analyzing your sentence…
        </p>
      )}

      {teaching.error && (
        <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
          {teaching.error}
        </p>
      )}

      {teaching.data && (
        <div className="mt-2 space-y-2 text-sm text-zinc-700 dark:text-zinc-300">
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Why it is wrong here
            </h4>
            <p className="mt-0.5">{teaching.data.why_wrong}</p>
          </section>
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Rule
            </h4>
            <p className="mt-0.5">{teaching.data.grammar_rule}</p>
          </section>
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Recommended correction
            </h4>
            <p className="mt-0.5 font-medium text-zinc-900 dark:text-zinc-100">
              {teaching.data.recommended_correction}
            </p>
          </section>
          {teaching.data.personalized_note && (
            <section>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                Your pattern
              </h4>
              <p className="mt-0.5">{teaching.data.personalized_note}</p>
            </section>
          )}
          <p className="text-xs text-zinc-400 dark:text-zinc-500">
            Edit the text yourself to fix it — the highlight clears when your correction is
            valid. Shortcuts: Alt+R reveal · Alt+T teach · Alt+I ignore.
          </p>
        </div>
      )}
    </div>
  );
}
