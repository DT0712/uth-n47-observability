// Giữ token và người đang đăng nhập cho cả ứng dụng.
// Token nằm trong bộ nhớ + sessionStorage (đóng tab là mất) theo docs/02-thiet-ke/kien-truc-portal.md mục 3.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setToken, setUnauthorizedHandler } from "../api/client";
import * as endpoints from "../api/endpoints";
import type { User } from "../types";

const KEY = "obslab.token";

interface AuthState {
  user: User | null;
  ready: boolean; // đã kiểm xong token cũ trong sessionStorage chưa
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function storage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  const clear = useCallback(() => {
    setToken(null);
    storage()?.removeItem(KEY);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(clear); // token hết hạn hoặc tài khoản bị khóa -> về trang đăng nhập
    const saved = storage()?.getItem(KEY);
    if (!saved) {
      setReady(true);
      return;
    }
    setToken(saved);
    endpoints
      .me()
      .then(setUser)
      .catch(clear)
      .finally(() => setReady(true));
    return () => setUnauthorizedHandler(null);
  }, [clear]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await endpoints.login(username, password);
    setToken(res.access_token);
    storage()?.setItem(KEY, res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await endpoints.logout(); // chỉ để ghi nhật ký; JWT không thu hồi được
    } catch {
      /* bỏ qua */
    }
    clear();
  }, [clear]);

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải nằm trong <AuthProvider>");
  return ctx;
}
