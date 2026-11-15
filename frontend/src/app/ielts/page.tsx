import { RequireAuth } from "@/features/auth/require-auth";
import { IeltsPage } from "@/features/ielts/ielts-page";

export default function IeltsRoute() {
  return (
    <RequireAuth>
      <IeltsPage />
    </RequireAuth>
  );
}
