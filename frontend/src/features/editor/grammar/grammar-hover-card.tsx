"use client";

/**
 * Floating grammar feedback card (user decision 2026-11-15 §2.4–2.6).
 *
 * Appears on hover over an underlined error; slightly transparent surface
 * floating above content. The correction stays blurred until the user clicks
 * it directly (no reveal button). After reveal, Tab replaces the original
 * text — only while this correction interaction is active. A small teaching
 * icon opens the contextual teaching card.
 */

import type { RevealedSuggestion } from "@/types/api";

export interface HoverCardState {
  issueId: string;
  top: number;
  left: number;
  explanation: string | null;
  revealed: RevealedSuggestion[] | null;
  pinned: boolean;
}

export function GrammarHoverCard({
  state,
  onRevealAnswer,
  onTeach,
  onMouseEnter,
  onMouseLeave,
}: {
  state: HoverCardState;
  onRevealAnswer: () => void;
  onTeach: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const recommended =
    state.revealed?.find((s) => s.is_recommended) ?? state.revealed?.[0] ?? null;

  return (
    <div
      data-testid="grammar-hover-card"
      className="awc-hint-card fixed z-40 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-zinc-200/70 bg-white/90 p-3 shadow-lg backdrop-blur-sm dark:border-zinc-700/70 dark:bg-zinc-900/90"
      style={{
        top: Math.min(state.top + 6, window.innerHeight - 160),
        left: Math.max(8, Math.min(state.left, window.innerWidth - 340)),
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <p className="text-xs leading-relaxed text-zinc-700 dark:text-zinc-300">
        {state.explanation ?? ""}
      </p>

      <div className="mt-2 flex items-center gap-2">
        {recommended ? (
          <span
            data-testid="revealed-answer"
            className="rounded bg-emerald-50 px-1.5 py-0.5 text-sm font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
          >
            {recommended.suggested_text}
          </span>
        ) : (
          <button
            type="button"
            data-testid="blurred-answer"
            onClick={onRevealAnswer}
            title="Click to see the suggested correction"
            className="awc-blurred-answer rounded bg-zinc-100 px-1.5 py-0.5 text-sm font-semibold text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
          >
            ••••
          </button>
        )}

        <button
          type="button"
          aria-label="Explain this error"
          data-testid="teaching-icon"
          onClick={onTeach}
          className="ml-auto flex h-6 w-6 items-center justify-center rounded-full border border-zinc-300 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 dark:border-zinc-600 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 2L1 7l11 5 9-4.09V17h2V7L12 2zM5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82z"
              fill="currentColor"
            />
          </svg>
        </button>
      </div>

      {recommended && (
        <p
          data-testid="tab-instruction"
          className="mt-2 text-[11px] font-medium text-zinc-500 dark:text-zinc-400"
        >
          Press <kbd className="rounded border border-zinc-300 px-1 dark:border-zinc-600">Tab</kbd>{" "}
          to replace the original text.
        </p>
      )}
      <p className="mt-1 text-[10px] text-zinc-400 dark:text-zinc-500">
        Alt+I ignore · Alt+T teach · Esc close
      </p>
    </div>
  );
}
