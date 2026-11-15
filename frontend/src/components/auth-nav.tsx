"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/features/auth/auth-provider";

export function AuthNav() {
  const { status, user, logout } = useAuth();
  const router = useRouter();

  if (status === "loading") {
    return <p className="text-sm text-zinc-400">…</p>;
  }

  if (status === "authenticated") {
    return (
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/dashboard"
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          我的作文
        </Link>
        <Link
          href="/knowledge"
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          知识库
        </Link>
        <Link
          href="/learning"
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          学习中心
        </Link>
        <Link
          href="/ielts"
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          IELTS 题库
        </Link>
        <Link
          href="/billing"
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          订阅
        </Link>
        <Link
          href="/profile"
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          {user?.display_name ?? "个人中心"}
        </Link>
        <button
          type="button"
          onClick={() => {
            void logout().then(() => router.replace("/login"));
          }}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          退出登录
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <Link
        href="/login"
        className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
      >
        登录
      </Link>
      <Link
        href="/register"
        className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        注册账号
      </Link>
    </div>
  );
}
