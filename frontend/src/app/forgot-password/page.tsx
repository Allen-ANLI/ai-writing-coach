"use client";

import { useState } from "react";
import Link from "next/link";

import { requestPasswordReset } from "@/services/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败，请稍后重试。");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          重置密码
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          输入注册邮箱，我们会发送重置链接。
        </p>
      </div>

      {sent ? (
        <div
          className="w-full max-w-sm rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
          data-testid="reset-sent"
        >
          如果 {email} 存在对应账号，重置链接已发送。链接一小时内有效，且只能使用一次。
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4" data-testid="forgot-form">
          <label className="block text-sm">
            <span className="text-xs font-medium text-zinc-500">邮箱</span>
            <input
              type="email"
              required
              data-testid="forgot-email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          {error && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
          <button
            type="submit"
            data-testid="forgot-submit"
            disabled={pending}
            className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {pending ? "发送中…" : "发送重置链接"}
          </button>
        </form>
      )}

      <Link href="/login" className="text-sm text-zinc-500 underline dark:text-zinc-400">
        返回登录
      </Link>
    </main>
  );
}
