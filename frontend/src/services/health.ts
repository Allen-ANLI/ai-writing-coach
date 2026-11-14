import { API_BASE_URL } from "@/lib/config";
import type { ErrorResponse, HealthResponse } from "@/types/api";

export type HealthResult =
  | { state: "healthy"; data: HealthResponse["data"] }
  | { state: "unhealthy"; status: number; error: ErrorResponse["error"] | null }
  | { state: "unreachable"; message: string };

export async function fetchHealth(): Promise<HealthResult> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  } catch {
    return {
      state: "unreachable",
      message: `Backend is not reachable at ${API_BASE_URL}.`,
    };
  }

  if (response.ok) {
    const body = (await response.json()) as HealthResponse;
    return { state: "healthy", data: body.data };
  }

  let error: ErrorResponse["error"] | null = null;
  try {
    const body = (await response.json()) as ErrorResponse;
    error = body.error ?? null;
  } catch {
    // Error body was not JSON; keep the status code as the only signal.
  }
  return { state: "unhealthy", status: response.status, error };
}
