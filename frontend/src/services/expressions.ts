import { apiFetch } from "@/lib/api-client";
import type {
  AcceptExpressionSuggestionRequest,
  AcceptExpressionSuggestionResponse,
  CreateExpressionRequest,
  ExpressionListResponse,
  ExpressionResponse,
  PolishRequest,
  SuggestionResponse,
  TranslationRequest,
} from "@/types/api";

export function listExpressions(params: {
  limit?: number;
  cursor?: string;
  status?: string;
  topic?: string;
  query?: string;
}): Promise<ExpressionListResponse> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.cursor) search.set("cursor", params.cursor);
  if (params.status) search.set("status", params.status);
  if (params.topic) search.set("topic", params.topic);
  if (params.query) search.set("query", params.query);
  const qs = search.toString();
  return apiFetch<ExpressionListResponse>(`/expressions${qs ? `?${qs}` : ""}`);
}

export function createExpression(payload: CreateExpressionRequest): Promise<ExpressionResponse> {
  return apiFetch<ExpressionResponse>("/expressions", { method: "POST", body: payload });
}

export function getExpression(expressionId: string): Promise<ExpressionResponse> {
  return apiFetch<ExpressionResponse>(`/expressions/${expressionId}`);
}

export function patchExpression(
  expressionId: string,
  payload: Record<string, unknown>,
): Promise<ExpressionResponse> {
  return apiFetch<ExpressionResponse>(`/expressions/${expressionId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteExpression(expressionId: string): Promise<void> {
  return apiFetch<void>(`/expressions/${expressionId}`, { method: "DELETE" });
}

export function archiveExpression(expressionId: string): Promise<ExpressionResponse> {
  return apiFetch<ExpressionResponse>(`/expressions/${expressionId}/archive`, { method: "POST" });
}

export function polishExpression(
  essayId: string,
  payload: PolishRequest,
): Promise<SuggestionResponse> {
  return apiFetch<SuggestionResponse>(`/essays/${essayId}/expression-suggestions`, {
    method: "POST",
    body: payload,
  });
}

export function translateChinese(
  essayId: string,
  payload: TranslationRequest,
): Promise<SuggestionResponse> {
  return apiFetch<SuggestionResponse>(`/essays/${essayId}/translations`, {
    method: "POST",
    body: payload,
  });
}

export function acceptExpressionSuggestion(
  essayId: string,
  suggestionId: string,
  payload: AcceptExpressionSuggestionRequest,
): Promise<AcceptExpressionSuggestionResponse> {
  return apiFetch<AcceptExpressionSuggestionResponse>(
    `/essays/${essayId}/expression-suggestions/${suggestionId}/accept`,
    { method: "POST", body: payload },
  );
}
