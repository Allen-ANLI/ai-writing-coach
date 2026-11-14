"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchHealth, type HealthResult } from "@/services/health";

function describe(result: HealthResult): { tone: "ok" | "bad"; text: string } {
  switch (result.state) {
    case "healthy":
      return {
        tone: "ok",
        text: `Backend healthy — status: ${result.data.status}, database: ${result.data.database}`,
      };
    case "unhealthy":
      return {
        tone: "bad",
        text: result.error
          ? `Backend responded ${result.status}: ${result.error.code} — ${result.error.message}`
          : `Backend responded ${result.status} without a JSON error envelope.`,
      };
    case "unreachable":
      return { tone: "bad", text: result.message };
  }
}

export function HealthStatus() {
  const [result, setResult] = useState<HealthResult | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void fetchHealth().then((next) => {
      if (!cancelled) {
        setResult(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const recheck = useCallback(async () => {
    setChecking(true);
    setResult(await fetchHealth());
    setChecking(false);
  }, []);

  const description = result === null ? null : describe(result);

  return (
    <section
      aria-label="Backend health"
      className="w-full max-w-xl rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Backend health
      </h2>
      <div role="status" aria-live="polite" className="mt-3 flex items-center gap-3">
        <span
          aria-hidden="true"
          className={`h-3 w-3 shrink-0 rounded-full ${
            description === null
              ? "bg-zinc-400 animate-pulse"
              : description.tone === "ok"
                ? "bg-emerald-500"
                : "bg-red-500"
          }`}
        />
        <p className="text-sm text-zinc-800 dark:text-zinc-200">
          {description === null ? "Checking backend…" : description.text}
        </p>
      </div>
      <button
        type="button"
        onClick={() => void recheck()}
        disabled={checking}
        className="mt-4 rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
      >
        {checking ? "Checking…" : "Re-check"}
      </button>
    </section>
  );
}
