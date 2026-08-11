import { apiFetch } from "./client";
import type { VideoJobResponse } from "@/lib/types/api";

export async function createVideo(resultId: string): Promise<{ video_job_id: string; status: string }> {
  return apiFetch("/api/v1/videos", {
    method: "POST",
    body: JSON.stringify({ result_id: resultId }),
  });
}

export async function getVideoStatus(videoJobId: string): Promise<VideoJobResponse> {
  return apiFetch(`/api/v1/videos/${videoJobId}`);
}
