/**
 * Fetch client with in-memory access token, single-flight refresh, and a
 * single automatic retry after 401.
 *
 * Security invariants:
 * - The access token lives ONLY in this module's memory (no localStorage /
 *   sessionStorage / cookies / logs).
 * - The refresh token is managed exclusively by the HttpOnly cookie; every
 *   request uses credentials: "include" and never touches the cookie value.
 * - Concurrent 401s share ONE refresh request (single-flight).
 * - The original request is retried at most once, and only on 401: the
 *   backend rejects unauthenticated requests before any business logic, so
 *   a retry cannot duplicate a side effect. Network errors and 5xx are never
 *   retried (non-idempotent safety).
 */

import { API_BASE_URL } from "@/lib/config";
import type { AuthResponse, ErrorDetail, ErrorResponse } from "@/types/api";

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetail[];

  constructor(status: number, code: string, message: string, details?: ErrorDetail[]) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details ?? [];
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
let authFailureHandler: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAuthFailureHandler(handler: (() => void) | null): void {
  authFailureHandler = handler;
}

// These endpoints must never trigger the automatic refresh flow themselves.
const NO_REFRESH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh"];

async function performRefresh(): Promise<string | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      return null;
    }
    const body = (await response.json()) as AuthResponse;
    return body.data.access_token;
  } catch {
    return null;
  }
}

/** Single-flight refresh: concurrent callers share one in-flight request. */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh()
      .then((token) => {
        if (token) {
          accessToken = token;
        }
        return token;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";

  const send = (token: string | null): Promise<Response> => {
    const headers: Record<string, string> = { ...options.headers };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return fetch(`${API_BASE_URL}${path}`, {
      method,
      credentials: "include",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  };

  let response = await send(accessToken);

  if (response.status === 401 && !NO_REFRESH_PATHS.includes(path)) {
    const token = await refreshAccessToken();
    if (token) {
      // Exactly one retry with the fresh token; no further refresh attempts.
      response = await send(token);
    } else {
      accessToken = null;
      authFailureHandler?.();
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body; fall through to the generic error below.
  }

  if (!response.ok) {
    const info = (body as ErrorResponse | null)?.error;
    throw new ApiClientError(
      response.status,
      info?.code ?? "UNKNOWN_ERROR",
      info?.message ?? `Request failed with status ${response.status}.`,
      info?.details,
    );
  }

  return body as T;
}
