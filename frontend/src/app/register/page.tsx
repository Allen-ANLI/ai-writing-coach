import Link from "next/link";

import { RegisterForm } from "@/features/auth/register-form";

export default function RegisterPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          注册账号
        </h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          开始你的英语写作训练。
        </p>
      </div>
      <RegisterForm />
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        已有账号？{" "}
        <Link href="/login" className="font-medium text-zinc-900 underline dark:text-zinc-100">
          登录
        </Link>
      </p>
    </main>
  );
}
