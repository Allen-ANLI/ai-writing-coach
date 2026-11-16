import { apiFetch } from "@/lib/api-client";
import type {
  PlannerChatResponse,
  PlannerMatchResponse,
  PlannerMessagesResponse,
} from "@/types/api";

export function sendPlannerMessage(
  essayId: string,
  message: string,
): Promise<PlannerChatResponse> {
  return apiFetch<PlannerChatResponse>(`/essays/${essayId}/planner/chat`, {
    method: "POST",
    body: { message },
  });
}

export function listPlannerMessages(essayId: string): Promise<PlannerMessagesResponse> {
  return apiFetch<PlannerMessagesResponse>(`/essays/${essayId}/planner/messages`);
}

export function matchGhostPosition(
  essayId: string,
  payload: { sentences: string[]; hints: string[] },
  signal?: AbortSignal,
): Promise<PlannerMatchResponse> {
  return apiFetch<PlannerMatchResponse>(`/essays/${essayId}/planner/match`, {
    method: "POST",
    body: payload,
    signal,
  });
}
