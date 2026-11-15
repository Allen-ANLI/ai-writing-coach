import { apiFetch } from "@/lib/api-client";
import type { PreferencesData, PreferencesResponse } from "@/types/api";

export function getPreferences(): Promise<PreferencesResponse> {
  return apiFetch<PreferencesResponse>("/users/me/preferences");
}

export function patchPreferences(payload: Partial<PreferencesData>): Promise<PreferencesResponse> {
  return apiFetch<PreferencesResponse>("/users/me/preferences", {
    method: "PATCH",
    body: payload,
  });
}
