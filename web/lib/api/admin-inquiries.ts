import { API_BASE } from "./client";
import type { Inquiry } from "./inquiries";

async function adminFetch<T>(
  path: string,
  adminKey: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      "X-Admin-Key": adminKey,
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let message = res.statusText;

    try {
      const body = await res.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch {
      // JSON 응답이 아니면 statusText 사용
    }

    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

export async function getAdminInquiries(adminKey: string): Promise<Inquiry[]> {
  return adminFetch("/api/v1/admin/inquiries", adminKey);
}

export async function answerInquiry(
  inquiryId: string,
  answer: string,
  adminKey: string,
): Promise<Inquiry> {
  return adminFetch(`/api/v1/admin/inquiries/${inquiryId}/answer`, adminKey, {
    method: "POST",
    body: JSON.stringify({ answer }),
  });
}

const ADMIN_KEY_STORAGE = "ad_studio_admin_key";

export function setAdminKey(adminKey: string | null) {
  if (typeof window === "undefined") return;

  if (adminKey) {
    window.sessionStorage.setItem(ADMIN_KEY_STORAGE, adminKey);
  } else {
    window.sessionStorage.removeItem(ADMIN_KEY_STORAGE);
  }
}

export function getAdminKey(): string | null {
  if (typeof window === "undefined") return null;

  return window.sessionStorage.getItem(ADMIN_KEY_STORAGE);
}
