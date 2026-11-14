import { Suspense } from "react";

import { RequireAuth } from "@/features/auth/require-auth";
import { EssayDetailRoute } from "@/features/essays/essay-detail";

export default function EssayDetailPage() {
  return (
    <RequireAuth>
      <Suspense
        fallback={
          <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12">
            <p role="status" className="text-sm text-zinc-500 dark:text-zinc-400">
              Loading essay…
            </p>
          </main>
        }
      >
        <EssayDetailRoute />
      </Suspense>
    </RequireAuth>
  );
}
