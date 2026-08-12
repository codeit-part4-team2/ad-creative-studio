"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { login as apiLogin, logout as apiLogout, me as apiMe, type Customer } from "@/lib/api/auth";
import { setAuthToken, getAuthToken } from "@/lib/api/client";

interface AuthContextValue {
  customer: Customer | null;
  isLoading: boolean;
  login: (customerId: string, pin: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    // .then()으로 감싸서 setState가 effect 본문에서 "동기적으로" 호출되지 않게 한다
    // (react-hooks/set-state-in-effect 규칙 - cascading render 방지 권고).
    Promise.resolve().then(async () => {
      const token = getAuthToken();
      if (!token) {
        if (!cancelled) setIsLoading(false);
        return;
      }
      try {
        const c = await apiMe();
        if (!cancelled) setCustomer(c);
      } catch {
        setAuthToken(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (customerId: string, pin: string) => {
    const res = await apiLogin(customerId, pin);
    setAuthToken(res.token);
    setCustomer(res.customer);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // 토큰이 이미 만료됐어도 로컬 상태는 정리한다
    }
    setAuthToken(null);
    setCustomer(null);
  }, []);

  return (
    <AuthContext.Provider value={{ customer, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth는 AuthProvider 안에서만 쓸 수 있습니다");
  return ctx;
}
