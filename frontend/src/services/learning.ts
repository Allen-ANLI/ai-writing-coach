import { apiFetch } from "@/lib/api-client";
import type {
  DueReviewsResponse,
  LearningSummaryResponse,
  ProgressResponse,
  ReviewResultResponse,
  WeaknessListResponse,
} from "@/types/api";

export function dueReviews(limit = 20): Promise<DueReviewsResponse> {
  return apiFetch<DueReviewsResponse>(`/learning/reviews/due?limit=${limit}`);
}

export function submitReview(
  expressionId: string,
  userAnswer: string,
): Promise<ReviewResultResponse> {
  return apiFetch<ReviewResultResponse>("/learning/reviews", {
    method: "POST",
    body: { expression_id: expressionId, user_answer: userAnswer, exercise_mode: "translation" },
  });
}

export function expressionProgress(expressionId: string): Promise<ProgressResponse> {
  return apiFetch<ProgressResponse>(`/expressions/${expressionId}/progress`);
}

export function learningSummary(): Promise<LearningSummaryResponse> {
  return apiFetch<LearningSummaryResponse>("/learning/summary");
}

export function weaknesses(): Promise<WeaknessListResponse> {
  return apiFetch<WeaknessListResponse>("/users/me/weaknesses");
}
