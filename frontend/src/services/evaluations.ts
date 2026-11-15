import { apiFetch } from "@/lib/api-client";
import type {
  AcceptRewriteResponse,
  EvaluationListResponse,
  EvaluationQueuedResponse,
  EvaluationResponse,
  EvaluationType,
  ModificationLevel,
  RewriteQueuedResponse,
  RewriteResponse,
} from "@/types/api";

export function queueEvaluation(
  essayId: string,
  payload: {
    version_id: string;
    evaluation_type: EvaluationType;
    task_type?: "task1" | "task2" | null;
  },
): Promise<EvaluationQueuedResponse> {
  return apiFetch<EvaluationQueuedResponse>(`/essays/${essayId}/evaluations`, {
    method: "POST",
    body: payload,
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}

export function listEvaluations(essayId: string): Promise<EvaluationListResponse> {
  return apiFetch<EvaluationListResponse>(`/essays/${essayId}/evaluations`);
}

export function getEvaluation(evaluationId: string): Promise<EvaluationResponse> {
  return apiFetch<EvaluationResponse>(`/evaluations/${evaluationId}`);
}

export function deleteEvaluation(evaluationId: string): Promise<void> {
  return apiFetch<void>(`/evaluations/${evaluationId}`, { method: "DELETE" });
}

export function queueRewrite(
  evaluationId: string,
  modificationLevel: ModificationLevel,
): Promise<RewriteQueuedResponse> {
  return apiFetch<RewriteQueuedResponse>(`/evaluations/${evaluationId}/rewrite`, {
    method: "POST",
    body: { modification_level: modificationLevel },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}

export function getRewrite(rewriteId: string): Promise<RewriteResponse> {
  return apiFetch<RewriteResponse>(`/rewrites/${rewriteId}`);
}

export function acceptRewrite(
  rewriteId: string,
  baseRevision: number,
): Promise<AcceptRewriteResponse> {
  return apiFetch<AcceptRewriteResponse>(`/rewrites/${rewriteId}/accept`, {
    method: "POST",
    body: { base_revision: baseRevision, client_revision: baseRevision },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}
