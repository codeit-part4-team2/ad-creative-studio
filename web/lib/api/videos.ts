import { apiFetch } from "./client";
import type { VideoJobResponse } from "@/lib/types/api";

export async function createVideo(
  resultId: string,
): Promise<{ video_job_id: string; render_status: string }> {
  return apiFetch("/api/v1/videos", {
    method: "POST",
    body: JSON.stringify({ result_id: resultId }),
  });
}

export async function getVideoStatus(
  videoJobId: string,
): Promise<VideoJobResponse> {
  return apiFetch(`/api/v1/videos/${videoJobId}`);
}

export async function approveVideo(
  videoJobId: string,
  payload: {
    activation_at: string;
    publish_to_youtube: boolean;
    pronunciation_confirmed: boolean;
  },
): Promise<VideoJobResponse> {
  return apiFetch(`/api/v1/videos/${videoJobId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}