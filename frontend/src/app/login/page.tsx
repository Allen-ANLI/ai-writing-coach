import Link from "next/link";

import { LoginForm } from "@/features/auth/login-form";

export default function LoginPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          登录
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          欢迎回到 AI Writing Coach。
        </p>
      </div>
      <LoginForm />
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        <Link href="/forgot-password" className="font-medium text-zinc-900 underline dark:text-zinc-100">
          忘记密码？
        </Link>
      </p>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        还没有账号？{" "}
        <Link href="/register" className="font-medium text-zinc-900 underline dark:text-zinc-100">
          立即注册
        </Link>
      </p>
    </main>
  );
}
