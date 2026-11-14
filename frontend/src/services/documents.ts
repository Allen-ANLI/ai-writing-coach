import { apiFetch } from "@/lib/api-client";
import type {
  CreateSnapshotRequest,
  RestoreRequest,
  RestoreResponse,
  SaveWorkingDocumentRequest,
  VersionListResponse,
  VersionResponse,
  WorkingDocumentResponse,
  WorkingDocumentSavedResponse,
} from "@/types/api";

export function getWorkingDocument(essayId: string): Promise<WorkingDocumentResponse> {
  return apiFetch<WorkingDocumentResponse>(`/essays/${essayId}/working-document`);
}

export function saveWorkingDocument(
  essayId: string,
  payload: SaveWorkingDocumentRequest,
): Promise<WorkingDocumentSavedResponse> {
  return apiFetch<WorkingDocumentSavedResponse>(`/essays/${essayId}/working-document`, {
    method: "PUT",
    body: payload,
  });
}

export function createSnapshot(
  essayId: string,
  payload: CreateSnapshotRequest,
  idempotencyKey?: string,
): Promise<VersionResponse> {
  return apiFetch<VersionResponse>(`/essays/${essayId}/snapshots`, {
    method: "POST",
    body: payload,
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

export function listVersions(
  essayId: string,
  limit = 50,
  cursor?: string,
): Promise<VersionListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.set("cursor", cursor);
  }
  return apiFetch<VersionListResponse>(`/essays/${essayId}/versions?${params.toString()}`);
}

export function getVersion(essayId: string, versionId: string): Promise<VersionResponse> {
  return apiFetch<VersionResponse>(`/essays/${essayId}/versions/${versionId}`);
}

export function restoreVersion(
  essayId: string,
  payload: RestoreRequest,
): Promise<RestoreResponse> {
  return apiFetch<RestoreResponse>(`/essays/${essayId}/restore`, {
    method: "POST",
    body: payload,
  });
}
