import { RequireAuth } from "@/features/auth/require-auth";
import { KnowledgePage } from "@/features/knowledge/knowledge-page";

export default function KnowledgeRoute() {
  return (
    <RequireAuth>
      <KnowledgePage />
    </RequireAuth>
  );
}
