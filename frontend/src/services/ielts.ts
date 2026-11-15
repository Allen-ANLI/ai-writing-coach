import { apiFetch } from "@/lib/api-client";
import type {
  IeltsFavoriteResponse,
  IeltsQuestionDetailResponse,
  IeltsQuestionListResponse,
  IeltsTagListResponse,
} from "@/types/api";

export interface IeltsQuestionFilters {
  limit?: number;
  cursor?: string;
  task_type?: string;
  topic?: string;
  question_type?: string;
}

export function listIeltsQuestions(filters: IeltsQuestionFilters = {}): Promise<IeltsQuestionListResponse> {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));
  if (filters.cursor) params.set("cursor", filters.cursor);
  if (filters.task_type) params.set("task_type", filters.task_type);
  if (filters.topic) params.set("topic", filters.topic);
  if (filters.question_type) params.set("question_type", filters.question_type);
  const query = params.toString();
  return apiFetch<IeltsQuestionListResponse>(`/ielts/questions${query ? `?${query}` : ""}`);
}

export function getIeltsQuestion(questionId: string): Promise<IeltsQuestionDetailResponse> {
  return apiFetch<IeltsQuestionDetailResponse>(`/ielts/questions/${questionId}`);
}

export function randomIeltsQuestion(): Promise<IeltsQuestionDetailResponse> {
  return apiFetch<IeltsQuestionDetailResponse>("/ielts/questions/random");
}

export function listIeltsTags(): Promise<IeltsTagListResponse> {
  return apiFetch<IeltsTagListResponse>("/ielts/tags");
}

export function favoriteIeltsQuestion(questionId: string): Promise<IeltsFavoriteResponse> {
  return apiFetch<IeltsFavoriteResponse>(`/ielts/questions/${questionId}/favorite`, {
    method: "POST",
  });
}

export function unfavoriteIeltsQuestion(questionId: string): Promise<void> {
  return apiFetch<void>(`/ielts/questions/${questionId}/favorite`, { method: "DELETE" });
}