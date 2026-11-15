import { apiFetch } from "@/lib/api-client";
import type {
  AiFeatureUsageListResponse,
  AiUsageTotalsResponse,
  AiUsageTrendsResponse,
} from "@/types/api";

export function aiUsageTotals(): Promise<AiUsageTotalsResponse> {
  return apiFetch<AiUsageTotalsResponse>("/analytics/ai-usage");
}

export function aiUsageByFeature(): Promise<AiFeatureUsageListResponse> {
  return apiFetch<AiFeatureUsageListResponse>("/analytics/ai-usage/by-feature");
}

export function aiUsageTrends(): Promise<AiUsageTrendsResponse> {
  return apiFetch<AiUsageTrendsResponse>("/analytics/ai-usage/trends");
}
