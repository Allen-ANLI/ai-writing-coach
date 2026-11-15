import { RequireAuth } from "@/features/auth/require-auth";
import { LearningPage } from "@/features/learning/learning-page";

export default function LearningRoute() {
  return (
    <RequireAuth>
      <LearningPage />
    </RequireAuth>
  );
}
