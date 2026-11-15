import { Suspense } from "react";

import { RequireAuth } from "@/features/auth/require-auth";
import { EditorRoute } from "@/features/editor/editor-route";

export default function EssayEditorPage() {
  return (
    <RequireAuth>
      <Suspense
        fallback={
          <main className="flex flex-1 items-center justify-center">
            <p role="status" className="text-sm text-zinc-500 dark:text-zinc-400">
              编辑器加载中…
            </p>
          </main>
        }
      >
        <EditorRoute />
      </Suspense>
    </RequireAuth>
  );
}
