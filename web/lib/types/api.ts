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
  video_job_id?: string | null;
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
  created_at?: number; // 백엔드가 실제로 내려주는 필드(유닉스 타임스탬프) - 최신순 정렬에 사용
}

export type VideoRenderStatus = "queued" | "processing" | "completed" | "failed";
export type VideoApprovalStatus = "pending" | "approved" | "rejected";
export type VideoPublishStatus =
  | "not_requested"
  | "pending"
  | "scheduled"
  | "failed"
  | "auth_required"
  | "needs_review"
  | "schedule_expired";

export interface VideoJobResponse {
  video_job_id: string;
  result_id: string;
  product_id: string;
  tone: Tone;
  time_slot: "commute_am" | "commute_pm";
  render_status: VideoRenderStatus;
  approval_status: VideoApprovalStatus;
  publish_status: VideoPublishStatus;
  video_url: string | null;
  script_version: string;
  script_lines: string[];
  tts_engine: string | null;
  tts_voice_preset: string | null;
  pronunciation_review_required: boolean;
  pronunciation_reviewed_at: string | null;
  scene_image_sha256s: string[];
  caption_layout_version: string | null;
  error_message: string | null;
}
