import { apiFetch } from "@/lib/api-client";
import type {
  AcceptIssueRequest,
  AcceptIssueResponse,
  GrammarCheckRequest,
  GrammarCheckResponse,
  IssueListResponse,
  IssueResponse,
  IssueValidationRequest,
  IssueValidationResponse,
  LiveAcceptRequest,
  RevealResponse,
  TeachingRequest,
  TeachingResponse,
} from "@/types/api";

export function grammarCheck(
  essayId: string,
  payload: GrammarCheckRequest,
  signal?: AbortSignal,
): Promise<GrammarCheckResponse> {
  return apiFetch<GrammarCheckResponse>(`/essays/${essayId}/grammar-check`, {
    method: "POST",
    body: payload,
    signal,
  });
}

export function listIssues(
  essayId: string,
  revision?: number,
  status?: string,
): Promise<IssueListResponse> {
  const params = new URLSearchParams();
  if (revision !== undefined) params.set("revision", String(revision));
  if (status) params.set("status", status);
  const query = params.toString();
  return apiFetch<IssueListResponse>(`/essays/${essayId}/issues${query ? `?${query}` : ""}`);
}

export function getIssue(essayId: string, issueId: string): Promise<IssueResponse> {
  return apiFetch<IssueResponse>(`/essays/${essayId}/issues/${issueId}`);
}

export function revealIssue(essayId: string, issueId: string): Promise<RevealResponse> {
  return apiFetch<RevealResponse>(`/essays/${essayId}/issues/${issueId}/reveal`, {
    method: "POST",
  });
}

export function ignoreIssue(essayId: string, issueId: string): Promise<IssueResponse> {
  return apiFetch<IssueResponse>(`/essays/${essayId}/issues/${issueId}`, {
    method: "PATCH",
    body: { status: "ignored" },
  });
}

export function validateIssue(
  essayId: string,
  payload: IssueValidationRequest,
): Promise<IssueValidationResponse> {
  return apiFetch<IssueValidationResponse>(`/essays/${essayId}/issues/validate`, {
    method: "POST",
    body: payload,
  });
}

export function requestTeaching(
  essayId: string,
  issueId: string,
  payload: TeachingRequest,
): Promise<TeachingResponse> {
  return apiFetch<TeachingResponse>(`/essays/${essayId}/issues/${issueId}/teaching`, {
    method: "POST",
    body: payload,
  });
}

export function acceptIssue(
  essayId: string,
  issueId: string,
  payload: AcceptIssueRequest,
): Promise<AcceptIssueResponse> {
  return apiFetch<AcceptIssueResponse>(`/essays/${essayId}/issues/${issueId}/accept`, {
    method: "POST",
    body: payload,
  });
}

export function liveAccept(
  essayId: string,
  payload: LiveAcceptRequest,
): Promise<AcceptIssueResponse> {
  return apiFetch<AcceptIssueResponse>(`/essays/${essayId}/issues/live-accept`, {
    method: "POST",
    body: payload,
  });
}
