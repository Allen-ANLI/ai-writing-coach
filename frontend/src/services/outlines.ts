import { apiFetch } from "@/lib/api-client";
import type {
  OutlineListResponse,
  OutlineNodeResponse,
  OutlineQueuedResponse,
  OutlineResponse,
} from "@/types/api";

export function generateOutline(
  essayId: string,
  payload: { viewpoint?: string | null; instructions?: string | null },
): Promise<OutlineQueuedResponse> {
  return apiFetch<OutlineQueuedResponse>(`/essays/${essayId}/outlines/generate`, {
    method: "POST",
    body: payload,
  });
}

export function listOutlines(essayId: string): Promise<OutlineListResponse> {
  return apiFetch<OutlineListResponse>(`/essays/${essayId}/outlines`);
}

export function getOutline(outlineId: string): Promise<OutlineResponse> {
  return apiFetch<OutlineResponse>(`/outlines/${outlineId}`);
}

export function patchOutline(
  outlineId: string,
  payload: { thesis_statement?: string | null },
): Promise<OutlineResponse> {
  return apiFetch<OutlineResponse>(`/outlines/${outlineId}`, { method: "PATCH", body: payload });
}

export function confirmOutline(outlineId: string): Promise<OutlineResponse> {
  return apiFetch<OutlineResponse>(`/outlines/${outlineId}/confirm`, { method: "POST" });
}

export function createOutlineNode(
  outlineId: string,
  payload: {
    parent_id?: string | null;
    node_type: "section" | "paragraph" | "sentence_idea";
    title: string;
    content?: string | null;
    sort_order?: number;
  },
): Promise<OutlineNodeResponse> {
  return apiFetch<OutlineNodeResponse>(`/outlines/${outlineId}/nodes`, {
    method: "POST",
    body: payload,
  });
}

export function patchOutlineNode(
  outlineId: string,
  nodeId: string,
  payload: { title?: string; content?: string | null; sort_order?: number },
): Promise<OutlineNodeResponse> {
  return apiFetch<OutlineNodeResponse>(`/outlines/${outlineId}/nodes/${nodeId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteOutlineNode(outlineId: string, nodeId: string): Promise<void> {
  return apiFetch<void>(`/outlines/${outlineId}/nodes/${nodeId}`, { method: "DELETE" });
}
