import { apiFetch } from "@/lib/api-client";
import type {
  PlannerChatResponse,
  PlannerMessagesResponse,
  PlannerProgressResponse,
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

export function judgeGhostProgress(
  essayId: string,
  payload: { sentence: string; idea_index: number; idea: string },
): Promise<PlannerProgressResponse> {
  return apiFetch<PlannerProgressResponse>(`/essays/${essayId}/planner/progress`, {
    method: "POST",
    body: payload,
  });
}
