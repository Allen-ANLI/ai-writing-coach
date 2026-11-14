"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  refreshAccessToken,
  setAccessToken,
  setAuthFailureHandler,
} from "@/lib/api-client";
import * as authService from "@/services/auth";
import type { UserSummary } from "@/types/api";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  user: UserSummary | null;
}

export interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string | null) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });
  const queryClient = useQueryClient();

  const clearSession = useCallback(() => {
    setAccessToken(null);
    // Drop cached server data so the next user never sees the previous
    // user's profile or sessions, even for a frame.
    queryClient.clear();
    setState({ status: "unauthenticated", user: null });
  }, [queryClient]);

  useEffect(() => {
    // Any failed refresh during an API call drops the whole auth state.
    setAuthFailureHandler(clearSession);

    // Restore the session after a page reload: the access token is gone from
    // memory, but the HttpOnly refresh cookie survives. One silent refresh
    // (single-flight) re-establishes the session without user interaction.
    let cancelled = false;
    void refreshAccessToken().then(async (token) => {
      if (cancelled) {
        return;
      }
      if (!token) {
        setState({ status: "unauthenticated", user: null });
        return;
      }
      try {
        const me = await authService.fetchMe();
        if (!cancelled) {
          setState({
            status: "authenticated",
            user: {
              id: me.data.id,
              email: me.data.email,
              display_name: me.data.profile.display_name,
            },
          });
        }
      } catch {
        if (!cancelled) {
          clearSession();
        }
      }
    });

    return () => {
      cancelled = true;
      setAuthFailureHandler(null);
    };
  }, [clearSession]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await authService.login(email, password);
    setAccessToken(response.data.access_token);
    setState({ status: "authenticated", user: response.data.user });
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string | null) => {
      const response = await authService.register(email, password, displayName);
      setAccessToken(response.data.access_token);
      setState({ status: "authenticated", user: response.data.user });
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      // Best effort: the local session is cleared even if the revocation
      // call fails (e.g. network down or token already expired).
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, register, logout }),
    [state, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return context;
}
