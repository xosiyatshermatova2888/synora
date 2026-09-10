"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  authApi,
  clearSession,
  getAccessToken,
  setAccessToken,
  UserOut,
} from "./api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: UserOut | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    let cancelled = false;

    void (async () => {
      // Restore the session: from the in-memory token if present, otherwise
      // via a silent refresh using the httpOnly cookie (hard-reload case).
      let u: UserOut | null = null;
      if (getAccessToken()) {
        try {
          u = await authApi.me();
        } catch {
          u = null;
        }
      }
      if (!u) {
        const restored = await authApi.refresh();
        if (restored) {
          try {
            u = await authApi.me();
          } catch {
            clearSession();
            u = null;
          }
        }
      }
      if (cancelled || !aliveRef.current) return;
      if (u) {
        setUser(u);
        setStatus("authenticated");
      } else {
        setUser(null);
        setStatus("unauthenticated");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const loadUser = useCallback(async () => {
    try {
      const u = await authApi.me();
      setUser(u);
      setStatus("authenticated");
    } catch {
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await authApi.login(email, password);
      setAccessToken(res.access_token);
      const u = await authApi.me();
      setUser(u);
      setStatus("authenticated");
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearSession();
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const refresh = useCallback(async () => {
    await loadUser();
  }, [loadUser]);

  const can = useCallback(
    (permission: string) => user?.permissions.includes(permission) ?? false,
    [user]
  );

  return (
    <AuthContext.Provider value={{ user, status, login, logout, refresh, can }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}