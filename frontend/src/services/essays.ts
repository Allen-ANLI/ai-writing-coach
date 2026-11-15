import { apiFetch } from "@/lib/api-client";
import type { EssayListResponse, EssayResponse, WritingType } from "@/types/api";

export function listEssays(limit = 50, cursor?: string): Promise<EssayListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.set("cursor", cursor);
  }
  return apiFetch<EssayListResponse>(`/essays?${params.toString()}`);
}

export function createEssay(payload: {
  title: string | null;
  writing_type: WritingType;
  question_prompt?: string | null;
  question_id?: string | null;
}): Promise<EssayResponse> {
  return apiFetch<EssayResponse>("/essays", { method: "POST", body: payload });
}

export function getEssay(essayId: string): Promise<EssayResponse> {
  return apiFetch<EssayResponse>(`/essays/${essayId}`);
}

export function renameEssay(essayId: string, title: string | null): Promise<EssayResponse> {
  return apiFetch<EssayResponse>(`/essays/${essayId}`, { method: "PATCH", body: { title } });
}

export function deleteEssay(essayId: string): Promise<void> {
  return apiFetch<void>(`/essays/${essayId}`, { method: "DELETE" });
}
