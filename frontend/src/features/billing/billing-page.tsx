"use client";

/**
 * Billing & subscription (Directive §H, Slice 10, ADR-021). Payments run in
 * SANDBOX mode only: checkout creates a pending transaction and confirm
 * simulates the provider callback. No real money moves until activation is
 * explicitly approved.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  billingHistory,
  billingUsage,
  cancelSubscription,
  checkout,
  confirmPayment,
  getSubscription,
  listPlans,
} from "@/services/billing";
import type { CheckoutData } from "@/types/api";

function quotaLabel(value: number | null): string {
  return value === null ? "Unlimited" : String(value);
}

export function BillingPage() {
  const queryClient = useQueryClient();
  const [pendingCheckout, setPendingCheckout] = useState<CheckoutData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const plansQuery = useQuery({
    queryKey: ["billing-plans"],
    queryFn: async () => (await listPlans()).data.items,
  });
  const subscriptionQuery = useQuery({
    queryKey: ["billing-subscription"],
    queryFn: async () => (await getSubscription()).data,
  });
  const usageQuery = useQuery({
    queryKey: ["billing-usage"],
    queryFn: async () => (await billingUsage()).data,
  });
  const historyQuery = useQuery({
    queryKey: ["billing-history"],
    queryFn: async () => (await billingHistory()).data.items,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["billing-subscription"] });
    void queryClient.invalidateQueries({ queryKey: ["billing-usage"] });
    void queryClient.invalidateQueries({ queryKey: ["billing-history"] });
  };

  const errorMessage = (err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback;

  const startCheckout = useMutation({
    mutationFn: async (planCode: string) => checkout(planCode),
    onSuccess: (response) => {
      setPendingCheckout(response.data);
      setError(null);
    },
    onError: (err) => setError(errorMessage(err, "Checkout failed.")),
  });

  const confirm = useMutation({
    mutationFn: async () => confirmPayment(pendingCheckout?.transaction_id as string),
    onSuccess: () => {
      setPendingCheckout(null);
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err, "Payment confirmation failed.")),
  });

  const cancel = useMutation({
    mutationFn: async () => cancelSubscription(),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: (err) => setError(errorMessage(err, "Cancellation failed.")),
  });

  const subscription = subscriptionQuery.data;
  const usage = usageQuery.data;

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10" data-testid="billing-page">
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Billing & subscription
      </h1>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
        Payments are in sandbox mode — no real charges. Quotas reset monthly.
      </p>

      {subscription && (
        <section
          className="mt-6 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
          data-testid="current-subscription"
        >
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            Current plan: <strong>{subscription.plan_name}</strong> · {subscription.status}
            {subscription.cancelled_at && " (access until period end)"}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            Period: {new Date(subscription.current_period_start).toLocaleDateString()} –{" "}
            {new Date(subscription.current_period_end).toLocaleDateString()}
          </p>
          {subscription.plan_code !== "free" && subscription.status === "active" && (
            <button
              type="button"
              data-testid="cancel-subscription"
              disabled={cancel.isPending}
              onClick={() => cancel.mutate()}
              className="mt-3 rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              Cancel subscription
            </button>
          )}
        </section>
      )}

      {usage && (
        <section className="mt-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800" data-testid="quota-usage">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
            This month&apos;s usage
          </p>
          <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
            AI calls: {usage.ai_calls} / {quotaLabel(usage.quota_ai_calls_monthly)} · Evaluations:{" "}
            {usage.evaluations} / {quotaLabel(usage.quota_evaluations_monthly)}
          </p>
        </section>
      )}

      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {pendingCheckout && (
        <section
          className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950"
          data-testid="sandbox-checkout"
        >
          <p className="text-sm text-amber-900 dark:text-amber-200">
            Sandbox checkout: {pendingCheckout.plan_code} — {pendingCheckout.currency}{" "}
            {pendingCheckout.amount}. Confirm to simulate the payment callback.
          </p>
          <div className="mt-3 flex gap-3">
            <button
              type="button"
              data-testid="confirm-payment"
              disabled={confirm.isPending}
              onClick={() => confirm.mutate()}
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {confirm.isPending ? "Confirming…" : "Confirm sandbox payment"}
            </button>
            <button
              type="button"
              data-testid="dismiss-checkout"
              onClick={() => setPendingCheckout(null)}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              Dismiss
            </button>
          </div>
        </section>
      )}

      <section className="mt-8" aria-label="Plans">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Plans</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-3" data-testid="plan-list">
          {plansQuery.data?.map((plan) => (
            <div
              key={plan.id}
              data-testid="plan-card"
              className={`rounded-lg border p-4 ${
                subscription?.plan_code === plan.code
                  ? "border-emerald-400 dark:border-emerald-700"
                  : "border-zinc-200 dark:border-zinc-800"
              }`}
            >
              <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{plan.name}</p>
              <p className="mt-1 text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                ${plan.price_monthly}
                <span className="text-xs font-normal text-zinc-500">/month</span>
              </p>
              <p className="mt-2 text-xs text-zinc-500">
                {quotaLabel(plan.quota_ai_calls_monthly)} AI calls ·{" "}
                {quotaLabel(plan.quota_evaluations_monthly)} evaluations
              </p>
              {subscription?.plan_code === plan.code ? (
                <p className="mt-3 text-xs font-medium text-emerald-600 dark:text-emerald-400" data-testid="current-plan-badge">
                  Current plan
                </p>
              ) : (
                plan.code !== "free" && (
                  <button
                    type="button"
                    data-testid={`upgrade-${plan.code}`}
                    disabled={startCheckout.isPending}
                    onClick={() => startCheckout.mutate(plan.code)}
                    className="mt-3 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
                  >
                    Upgrade (sandbox)
                  </button>
                )
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8" aria-label="Billing history">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Billing history
        </h2>
        {historyQuery.data && historyQuery.data.length === 0 && (
          <p className="mt-3 text-sm text-zinc-500" data-testid="no-history">
            No transactions yet.
          </p>
        )}
        <ul className="mt-3 space-y-2" data-testid="history-list">
          {historyQuery.data?.map((transaction) => (
            <li
              key={transaction.id}
              data-testid="history-item"
              className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
            >
              <span className="text-zinc-700 dark:text-zinc-300">
                {transaction.kind} · {transaction.provider}
              </span>
              <span className="text-xs text-zinc-500">
                {transaction.currency} {transaction.amount} · {transaction.status} ·{" "}
                {new Date(transaction.created_at).toLocaleDateString()}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
