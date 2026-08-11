// 모든 API 호출의 공용 통로. Streamlit의 API_BASE 패턴과 동일한 역할 —
// 하나만 바꾸면 어디를 가리킬지 다 바뀐다.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
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
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** 백엔드가 내려주는 상대경로("/files/...")를 절대 URL로 바꾼다 (이미지·영상 표시용). */
export function resolveAssetUrl(url: string): string {
  return url.startsWith("/") ? `${API_BASE}${url}` : url;
}
