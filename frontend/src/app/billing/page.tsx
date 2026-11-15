import { RequireAuth } from "@/features/auth/require-auth";
import { BillingPage } from "@/features/billing/billing-page";

export default function BillingRoute() {
  return (
    <RequireAuth>
      <BillingPage />
    </RequireAuth>
  );
}
