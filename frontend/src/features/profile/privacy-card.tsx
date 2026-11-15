"use client";

/**
 * Data & privacy controls (R9, PRD §9.3): full JSON export and irreversible
 * account deletion with explicit confirmation.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/features/auth/auth-provider";
import { deleteAccount, exportAccountData } from "@/services/auth";

export function PrivacyCard() {
  const router = useRouter();
  const { logout } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setBusy(true);
    setError(null);
    try {
      const data = await exportAccountData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "ai-writing-coach-export.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    setError(null);
    try {
      await deleteAccount();
      await logout();
      router.replace("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deletion failed.");
      setBusy(false);
    }
  }

  return (
    <section
      aria-label="Data and privacy"
      className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="privacy-card"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Data & privacy
      </h2>
      <div className="mt-3 flex flex-wrap gap-3">
        <button
          type="button"
          data-testid="export-data"
          disabled={busy}
          onClick={() => void handleExport()}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          Export my data (JSON)
        </button>
        {!confirming ? (
          <button
            type="button"
            data-testid="delete-account"
            disabled={busy}
            onClick={() => setConfirming(true)}
            className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
          >
            Delete account
          </button>
        ) : (
          <span className="flex items-center gap-2" data-testid="delete-confirm">
            <span className="text-xs text-red-600 dark:text-red-400">
              Permanently delete everything?
            </span>
            <button
              type="button"
              data-testid="confirm-delete"
              disabled={busy}
              onClick={() => void handleDelete()}
              className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {busy ? "Deleting…" : "Yes, delete"}
            </button>
            <button
              type="button"
              data-testid="cancel-delete"
              onClick={() => setConfirming(false)}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Cancel
            </button>
          </span>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
    </section>
  );
}
