import { apiFetch } from "./client";

export interface YouTubeStatusResponse {
  configured: boolean;
  connection_id: string;
  token_available: boolean;
}

export async function getYouTubeStatus(): Promise<YouTubeStatusResponse> {
  return apiFetch("/api/v1/youtube/status");
}