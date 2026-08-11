import { apiFetch } from "./client";
import type { HistoryEntry } from "@/lib/types/api";

export async function getHistory(favoriteOnly = false): Promise<HistoryEntry[]> {
  return apiFetch(`/api/v1/history?favorite_only=${favoriteOnly}`);
}

export async function toggleFavorite(jobId: string): Promise<HistoryEntry> {
  return apiFetch(`/api/v1/history/${jobId}/favorite`, { method: "PATCH" });
}

export function downloadOneUrl(jobId: string, tone: string, outputFormat: string, timeSlot?: string) {
  const params = new URLSearchParams({ tone, output_format: outputFormat });
  if (timeSlot) params.set("time_slot", timeSlot);
  return `/api/v1/download/${jobId}?${params.toString()}`;
}

export function downloadAllUrl(jobId: string) {
  return `/api/v1/download/${jobId}/all`;
}
