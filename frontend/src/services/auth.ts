import { apiFetch } from "@/lib/api-client";
import type { AuthResponse, MeResponse, SessionsResponse } from "@/types/api";

export function register(
  email: string,
  password: string,
  displayName: string | null,
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/register", {
    method: "POST",
    body: { email, password, display_name: displayName },
  });
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function fetchMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/users/me");
}

export function fetchSessions(): Promise<SessionsResponse> {
  return apiFetch<SessionsResponse>("/auth/sessions");
}

export function requestPasswordReset(email: string): Promise<{ data: { accepted: boolean } }> {
  return apiFetch<{ data: { accepted: boolean } }>("/auth/password-reset/request", {
    method: "POST",
    body: { email },
  });
}

export function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<{ data: { password_updated: boolean } }> {
  return apiFetch<{ data: { password_updated: boolean } }>("/auth/password-reset/confirm", {
    method: "POST",
    body: { token, new_password: newPassword },
  });
}

export function exportAccountData(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/users/me/export");
}

export function deleteAccount(): Promise<void> {
  return apiFetch<void>("/users/me", { method: "DELETE" });
}
