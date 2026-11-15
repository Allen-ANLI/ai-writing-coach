import { apiFetch } from "@/lib/api-client";
import type {
  LearningPlanListResponse,
  LearningPlanResponse,
  LearningTaskListResponse,
  LearningTaskResponse,
  LearningTaskStatus,
} from "@/types/api";

export function createPlan(payload: {
  title: string;
  goal?: string | null;
  daily_target_minutes?: number | null;
}): Promise<LearningPlanResponse> {
  return apiFetch<LearningPlanResponse>("/learning/plans", { method: "POST", body: payload });
}

export function listPlans(): Promise<LearningPlanListResponse> {
  return apiFetch<LearningPlanListResponse>("/learning/plans");
}

export function listTasks(): Promise<LearningTaskListResponse> {
  return apiFetch<LearningTaskListResponse>("/learning/tasks");
}

export function patchTask(
  taskId: string,
  payload: { status?: LearningTaskStatus; title?: string; description?: string | null },
): Promise<LearningTaskResponse> {
  return apiFetch<LearningTaskResponse>(`/learning/tasks/${taskId}`, {
    method: "PATCH",
    body: payload,
  });
}
