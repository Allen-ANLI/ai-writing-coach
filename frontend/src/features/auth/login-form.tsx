"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiClientError } from "@/lib/api-client";
import { useAuth } from "@/features/auth/auth-provider";

const inputClass =
  "w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:border-zinc-500 dark:focus:ring-zinc-800";

export function LoginForm() {
  const { status, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/profile");
    }
  }, [status, router]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login(email, password);
      router.replace("/profile");
    } catch (caught) {
      if (caught instanceof ApiClientError) {
        setError(
          caught.code === "INVALID_CREDENTIALS"
            ? "邮箱或密码错误。"
            : caught.code === "RATE_LIMIT_EXCEEDED"
              ? "尝试次数过多，请稍后再试。"
              : caught.message,
        );
      } else {
        setError("无法连接服务器，请稍后重试。");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4" noValidate={false}>
      <div>
        <label htmlFor="login-email" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          邮箱
        </label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={inputClass}
        />
      </div>
      <div>
        <label htmlFor="login-password" className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
          密码
        </label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={inputClass}
        />
      </div>
      {error && (
        <p role="alert" data-testid="auth-error" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        {pending ? "登录中…" : "登录"}
      </button>
    </form>
  );
}
