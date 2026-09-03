"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { LoginRequest, TokenPair, User } from "@sentinel/shared";
import { api, ApiError, endpoints } from "./api";
import { tokenStore } from "./token-store";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      // /auth/me transparently refreshes via the httpOnly cookie when the
      // access token has expired, so a reload restores the session silently.
      try {
        const me = await api.get<User>(endpoints.me);
        if (!cancelled) {
          setUser(me);
          setStatus("authenticated");
        }
      } catch {
        tokenStore.clear();
        if (!cancelled) setStatus("unauthenticated");
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    const pair = await api.post<TokenPair>(endpoints.login, credentials);
    tokenStore.set(pair.access_token);
    setUser(pair.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post(endpoints.logout);
    } catch {
      // network/API hiccups should not block local sign-out
    }
    tokenStore.clear();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo(
    () => ({ user, status, login, logout, setUser }),
    [user, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>.");
  return ctx;
}

export { ApiError };
export type { AuthStatus };