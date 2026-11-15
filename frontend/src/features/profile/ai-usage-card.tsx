"use client";

/**
 * AI usage analytics (API Spec §16, Slice 9): the signed-in user's own call
 * counts, token totals, estimated cost, per-feature breakdown and 14-day
 * trend. Rule-based checks are not LLM calls and never appear here.
 */

import { useQuery } from "@tanstack/react-query";

import { aiUsageByFeature, aiUsageTotals, aiUsageTrends } from "@/services/analytics";

export function AiUsageCard() {
  const totalsQuery = useQuery({
    queryKey: ["ai-usage-totals"],
    queryFn: async () => (await aiUsageTotals()).data,
  });
  const featuresQuery = useQuery({
    queryKey: ["ai-usage-features"],
    queryFn: async () => (await aiUsageByFeature()).data.items,
  });
  const trendsQuery = useQuery({
    queryKey: ["ai-usage-trends"],
    queryFn: async () => (await aiUsageTrends()).data.items,
  });

  const totals = totalsQuery.data;
  const maxCalls = Math.max(1, ...(trendsQuery.data ?? []).map((point) => point.calls));

  return (
    <section
      aria-label="AI usage"
      className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="ai-usage-card"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        AI usage
      </h2>
      {totalsQuery.isPending && <p className="mt-3 text-sm text-zinc-500">Loading…</p>}
      {totals && (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4" data-testid="usage-totals">
            <div>
              <dt className="text-xs text-zinc-500">AI calls</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{totals.total_calls}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Tokens (in/out)</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                {totals.input_tokens}/{totals.output_tokens}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Estimated cost</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                ${totals.estimated_cost.toFixed(4)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">Errors</dt>
              <dd className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{totals.error_calls}</dd>
            </div>
          </dl>

          {featuresQuery.data && featuresQuery.data.length > 0 && (
            <ul className="mt-4 space-y-1 text-xs text-zinc-600 dark:text-zinc-400" data-testid="usage-features">
              {featuresQuery.data.map((feature) => (
                <li key={feature.feature} className="flex justify-between">
                  <span>{feature.feature}</span>
                  <span>{feature.calls} calls · ${feature.estimated_cost.toFixed(4)}</span>
                </li>
              ))}
            </ul>
          )}

          {trendsQuery.data && (
            <div className="mt-4" data-testid="usage-trend">
              <p className="text-xs text-zinc-500">Last 14 days</p>
              <div className="mt-1 flex h-12 items-end gap-0.5">
                {trendsQuery.data.map((point) => (
                  <div
                    key={point.date}
                    title={`${point.date}: ${point.calls} calls`}
                    className="flex-1 rounded-t bg-zinc-300 dark:bg-zinc-700"
                    style={{ height: `${(point.calls / maxCalls) * 100}%`, minHeight: point.calls > 0 ? 4 : 1 }}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
