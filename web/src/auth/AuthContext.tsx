import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { setSessionExpiredHandler, tokens } from "../api/client";
import { authApi } from "../api/endpoints";
import { warmUp } from "../lib/prefetch";
import type { Role, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, role?: Role) => Promise<User>;
  logout: () => Promise<void>;
  /** Ask the server again who we are (e.g. after confirming the email). */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);
const USER_KEY = "ara_user";

function readCachedUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Start with the user remembered from last time, so the app opens at once instead of waiting for the server.
  const [user, setUserState] = useState<User | null>(() => (tokens.access ? readCachedUser() : null));
  const [loading, setLoading] = useState(() => Boolean(tokens.access) && !readCachedUser());
  const queryClient = useQueryClient();
  const setUser = useCallback((u: User | null) => {
    setUserState(u);
    try {
      if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
      else localStorage.removeItem(USER_KEY);
    } catch {
      /* private mode: just don't remember */
    }
  }, []);

  // On page load: if we have a token, check with the server who we are (in the background when remembered).
  useEffect(() => {
    if (!tokens.access) {
      setUser(null);
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch((err) => {
        // Only forget the login when the server says it is invalid, not when the network is slow or down.
        if (err?.response?.status === 401 || err?.response?.status === 403) {
          tokens.clear();
          setUser(null);
        }
      })
      .finally(() => setLoading(false));
  }, [setUser]);

  // Load the main pages of the portal in the background once we know who is logged in.
  const role = user?.role;
  useEffect(() => {
    if (role) warmUp(queryClient, role);
  }, [role, queryClient]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      queryClient.clear();
      if (!window.location.pathname.startsWith("/login")) window.location.assign("/login?expired=1");
    });
  }, [queryClient, setUser]);

  const login = useCallback(async (email: string, password: string, role?: Role) => {
    const res = await authApi.login(email, password, role);
    tokens.set(res.access_token, res.refresh_token);
    setUser(res.user);
    return res.user;
  }, [setUser]);

  const logout = useCallback(async () => {
    const refresh = tokens.refresh;
    tokens.clear();
    setUser(null);
    queryClient.clear();
    // Tell the server in the background; logging out locally is enough if that call fails.
    if (refresh) authApi.logout(refresh).catch(() => undefined);
  }, [queryClient, setUser]);

  const refreshUser = useCallback(async () => {
    if (tokens.access) setUser(await authApi.me());
  }, [setUser]);

  const value = useMemo(() => ({ user, loading, login, logout, refreshUser }), [user, loading, login, logout, refreshUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
