import { apiFetch } from "@/lib/api-client";
import type {
  WorkflowAction,
  WorkflowEventListResponse,
  WorkflowQueuedResponse,
  WorkflowResponse,
  WorkflowType,
} from "@/types/api";

export function createWorkflow(payload: {
  workflow_type: WorkflowType;
  essay_id?: string | null;
  input?: Record<string, unknown>;
}): Promise<WorkflowQueuedResponse> {
  return apiFetch<WorkflowQueuedResponse>("/workflows", { method: "POST", body: payload });
}

export function getWorkflow(workflowId: string): Promise<WorkflowResponse> {
  return apiFetch<WorkflowResponse>(`/workflows/${workflowId}`);
}

export function resumeWorkflow(
  workflowId: string,
  action: WorkflowAction,
  input: Record<string, unknown> = {},
): Promise<WorkflowResponse> {
  return apiFetch<WorkflowResponse>(`/workflows/${workflowId}/resume`, {
    method: "POST",
    body: { action, input },
  });
}

export function cancelWorkflow(workflowId: string): Promise<WorkflowResponse> {
  return apiFetch<WorkflowResponse>(`/workflows/${workflowId}/cancel`, { method: "POST" });
}

export function listWorkflowEvents(workflowId: string): Promise<WorkflowEventListResponse> {
  return apiFetch<WorkflowEventListResponse>(`/workflows/${workflowId}/events`);
}
