// 모든 API 호출의 공용 통로. Streamlit의 API_BASE 패턴과 동일한 역할 —
// 하나만 바꾸면 어디를 가리킬지 다 바뀐다.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const TOKEN_STORAGE_KEY = "ad_studio_token";

/** 로그인 시 저장, apiFetch가 매 요청마다 Authorization 헤더로 붙인다. */
export function setAuthToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ? JSON.stringify(body.detail) : detail;
    } catch {
      // 응답이 JSON이 아니면 statusText 그대로 사용
    }
    if (res.status === 401) setAuthToken(null); // 만료된 토큰을 계속 붙여서 재요청하지 않게 정리
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** 백엔드가 내려주는 상대경로("/files/...")를 절대 URL로 바꾼다 (이미지·영상 표시용). */
export function resolveAssetUrl(url: string): string {
  return url.startsWith("/") ? `${API_BASE}${url}` : url;
}
