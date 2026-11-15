import { apiFetch } from "@/lib/api-client";
import type {
  AcceptExpressionSuggestionRequest,
  AcceptExpressionSuggestionResponse,
  CreateExpressionRequest,
  EssaySuggestionListResponse,
  ExpressionListResponse,
  ExpressionResponse,
  ExtractionResponse,
  PolishRequest,
  PolishSentenceResponse,
  SuggestionResponse,
  TranslationRequest,
} from "@/types/api";

export function polishSentence(
  essayId: string,
  payload: {
    session_id: string;
    server_revision: number;
    client_revision: number;
    sentence: string;
    sentence_range: { start: number; end: number; offset_unit: "unicode_codepoint" };
    paragraph_context?: string | null;
    fragment_anchor?: string | null;
    exclude?: string[];
  },
): Promise<PolishSentenceResponse> {
  return apiFetch<PolishSentenceResponse>(`/essays/${essayId}/expressions/polish-sentence`, {
    method: "POST",
    body: payload,
  });
}

export function listEssaySuggestions(essayId: string): Promise<EssaySuggestionListResponse> {
  return apiFetch<EssaySuggestionListResponse>(`/essays/${essayId}/expression-suggestions`);
}

export function listExpressions(params: {
  limit?: number;
  cursor?: string;
  status?: string;
  topic?: string;
  query?: string;
  mode?: "keyword" | "semantic" | "hybrid";
}): Promise<ExpressionListResponse> {
  if (params.mode && params.mode !== "keyword" && params.query) {
    return apiFetch<ExpressionListResponse>("/expressions/search", {
      method: "POST",
      body: {
        query: params.query,
        mode: params.mode,
        status: params.status,
        topic: params.topic,
        limit: params.limit ?? 50,
      },
    });
  }
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.cursor) search.set("cursor", params.cursor);
  if (params.status) search.set("status", params.status);
  if (params.topic) search.set("topic", params.topic);
  if (params.query) search.set("query", params.query);
  const qs = search.toString();
  return apiFetch<ExpressionListResponse>(`/expressions${qs ? `?${qs}` : ""}`);
}

export function extractExpressions(
  essayId: string,
  payload: { version_id: string; extraction_scope?: "full" | "assisted_changes" },
): Promise<ExtractionResponse> {
  return apiFetch<ExtractionResponse>(`/essays/${essayId}/expressions/extract`, {
    method: "POST",
    body: payload,
  });
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
  signal?: AbortSignal,
): Promise<SuggestionResponse> {
  return apiFetch<SuggestionResponse>(`/essays/${essayId}/translations`, {
    method: "POST",
    body: payload,
    signal,
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
