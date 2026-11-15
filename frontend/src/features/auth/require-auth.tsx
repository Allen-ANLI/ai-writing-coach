"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/auth-provider";

/**
 * Client-side route guard. Unauthenticated visitors are redirected to /login;
 * while the silent session restore is in flight, nothing renders to avoid a
 * flash of protected content.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <main className="flex flex-1 items-center justify-center px-6 py-16">
        <p role="status" className="text-sm text-zinc-500 dark:text-zinc-400">
          {status === "loading" ? "正在恢复会话…" : "正在跳转到登录页…"}
        </p>
      </main>
    );
  }

  return <>{children}</>;
}
