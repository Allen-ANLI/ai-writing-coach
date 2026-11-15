import { apiFetch } from "@/lib/api-client";
import type {
  BillingHistoryResponse,
  BillingPlanListResponse,
  BillingUsageResponse,
  CheckoutResponse,
  SubscriptionResponse,
} from "@/types/api";

export function listPlans(): Promise<BillingPlanListResponse> {
  return apiFetch<BillingPlanListResponse>("/billing/plans");
}

export function getSubscription(): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>("/billing/subscription");
}

export function checkout(planCode: string): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>("/billing/checkout", {
    method: "POST",
    body: { plan_code: planCode },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}

export function confirmPayment(transactionId: string): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>("/billing/confirm", {
    method: "POST",
    body: { transaction_id: transactionId },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}

export function cancelSubscription(): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>("/billing/cancel", { method: "POST" });
}

export function billingHistory(): Promise<BillingHistoryResponse> {
  return apiFetch<BillingHistoryResponse>("/billing/history");
}

export function billingUsage(): Promise<BillingUsageResponse> {
  return apiFetch<BillingUsageResponse>("/billing/usage");
}
