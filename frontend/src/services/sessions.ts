import { apiFetch } from "@/lib/api-client";
import type {
  CreateSessionRequest,
  SessionListResponse,
  SessionResponse,
  SubmitSessionRequest,
  SubmitResponse,
} from "@/types/api";

export function listSessions(essayId: string): Promise<SessionListResponse> {
  return apiFetch<SessionListResponse>(`/essays/${essayId}/sessions`);
}

export function createSession(
  essayId: string,
  payload: CreateSessionRequest,
): Promise<SessionResponse> {
  return apiFetch<SessionResponse>(`/essays/${essayId}/sessions`, {
    method: "POST",
    body: payload,
  });
}

export function getSession(sessionId: string): Promise<SessionResponse> {
  return apiFetch<SessionResponse>(`/writing-sessions/${sessionId}`);
}

export function cancelSession(sessionId: string): Promise<SessionResponse> {
  return apiFetch<SessionResponse>(`/writing-sessions/${sessionId}`, {
    method: "PATCH",
    body: { status: "cancelled" },
  });
}

export function submitSession(
  sessionId: string,
  payload: SubmitSessionRequest,
  idempotencyKey?: string,
): Promise<SubmitResponse> {
  return apiFetch<SubmitResponse>(`/writing-sessions/${sessionId}/submit`, {
    method: "POST",
    body: payload,
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}
