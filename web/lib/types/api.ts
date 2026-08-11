// app/backend/schemas의 실제 응답 형태와 1:1로 맞춘 타입.
// 백엔드가 이미 완성돼 있으므로(app/backend), 여기서 새로 추측하지 않고 그대로 옮긴다.

export type Tone = "emotional" | "modern" | "practical" | "premium";

export type TimeSlot =
  | "morning"
  | "commute_am"
  | "afternoon"
  | "commute_pm"
  | "evening"
  | "late_night";

export const RUSH_HOUR_SLOTS: TimeSlot[] = ["commute_am", "commute_pm"];

export interface Product {
  product_id: string;
  image_url: string;
}

export interface ToneResult {
  result_id: string;
  tone: Tone;
  time_slot: TimeSlot | null;
  headline: string;
  subcopy: string;
  images: Record<string, string>; // output_format -> url
  video_url: string | null;
}

export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  completed_count: number;
  total_count: number;
  current_step: string | null;
  error_message?: string | null;
}

export interface GenerationResultResponse {
  job_id: string;
  status: JobStatus;
  results: ToneResult[];
}

export interface HistoryEntry {
  job_id: string;
  product_id: string;
  favorite: boolean;
  results: ToneResult[];
}

export type VideoJobStatus = "queued" | "processing" | "completed" | "failed";

export interface VideoJobResponse {
  video_job_id: string;
  status: VideoJobStatus;
  video_url: string | null;
  error_message: string | null;
}
