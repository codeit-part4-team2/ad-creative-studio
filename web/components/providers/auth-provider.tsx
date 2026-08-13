"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
  const queryClient = useQueryClient();

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

  useEffect(() => {
    // apiFetch가 401을 받으면 client.ts에서 이 이벤트를 쏜다 - 토큰만 지우고
    // React 상태(customer)는 그대로 두면, 화면은 계속 "로그인된 것처럼" 보이는데
    // 요청은 조용히 다 실패하는 상태가 된다 (PR 리뷰에서 지적됨). 여기서 받아서
    // 로그인 화면으로 확실히 돌려보낸다.
    function handleUnauthorized() {
      setCustomer(null);
      queryClient.clear();
    }
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, [queryClient]);

  const login = useCallback(
    async (customerId: string, pin: string) => {
      const res = await apiLogin(customerId, pin);
      setAuthToken(res.token);
      setCustomer(res.customer);
      // 같은 탭에서 계정을 바꿔 로그인하는 경우, 이전 고객사 데이터가 react-query
      // 캐시(staleTime 5초)에 남아있으면 새로 로그인한 화면에 잠깐 비칠 수 있다
      // (PR 리뷰에서 지적됨) - 로그인 성공 시 전부 지운다.
      queryClient.clear();
    },
    [queryClient]
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // 토큰이 이미 만료됐어도 로컬 상태는 정리한다
    }
    setAuthToken(null);
    setCustomer(null);
    queryClient.clear();
  }, [queryClient]);

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
