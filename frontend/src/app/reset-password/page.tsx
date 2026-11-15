"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { confirmPasswordReset } from "@/services/auth";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
      setTimeout(() => router.replace("/login"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败，请稍后重试。");
    } finally {
      setPending(false);
    }
  }

  if (!token) {
    return (
      <p className="text-sm text-red-600 dark:text-red-400" data-testid="reset-no-token">
        该重置链接缺少令牌。请从登录页重新申请。
      </p>
    );
  }

  if (done) {
    return (
      <p className="text-sm text-emerald-600 dark:text-emerald-400" data-testid="reset-done">
        密码已更新，正在跳转到登录页…
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4" data-testid="reset-form">
      <label className="block text-sm">
        <span className="text-xs font-medium text-zinc-500">新密码（至少 10 个字符）</span>
        <input
          type="password"
          required
          minLength={10}
          data-testid="reset-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400" data-testid="reset-error">
          {error}
        </p>
      )}
      <button
        type="submit"
        data-testid="reset-submit"
        disabled={pending}
        className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {pending ? "更新中…" : "设置新密码"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          设置新密码
        </h1>
      </div>
      <Suspense fallback={<p className="text-sm text-zinc-500">加载中…</p>}>
        <ResetPasswordForm />
      </Suspense>
      <Link href="/login" className="text-sm text-zinc-500 underline dark:text-zinc-400">
        返回登录
      </Link>
    </main>
  );
}
