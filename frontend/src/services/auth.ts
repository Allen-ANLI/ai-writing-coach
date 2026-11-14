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
