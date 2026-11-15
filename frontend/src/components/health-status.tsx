"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchHealth, type HealthResult } from "@/services/health";

function describe(result: HealthResult): { tone: "ok" | "bad"; text: string } {
  switch (result.state) {
    case "healthy":
      return {
        tone: "ok",
        text: `后端服务正常（数据库${result.data.database === "connected" ? "已连接" : "状态未知"}）`,
      };
    case "unhealthy":
      return {
        tone: "bad",
        text: result.error
          ? `后端返回 ${result.status}：${result.error.code} — ${result.error.message}`
          : `后端返回 ${result.status}，且没有标准错误信息。`,
      };
    case "unreachable":
      return { tone: "bad", text: "无法连接后端服务，请确认后端已启动（start-dev.ps1）。" };
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
      aria-label="后端健康状态"
      className="w-full max-w-xl rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        后端健康状态
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
          {description === null ? "正在检测后端…" : description.text}
        </p>
      </div>
      <button
        type="button"
        onClick={() => void recheck()}
        disabled={checking}
        className="mt-4 rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
      >
        {checking ? "检测中…" : "重新检测"}
      </button>
    </section>
  );
}
