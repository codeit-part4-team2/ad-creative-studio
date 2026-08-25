import type { VideoJobResponse } from "./types/api";

type PublishState = Pick<
  VideoJobResponse,
  "approval_status" | "publish_status"
>;

type PronunciationState = Pick<
  VideoJobResponse,
  "pronunciation_review_required" | "pronunciation_reviewed_at"
>;

const RETRYABLE_PUBLISH_STATUSES = new Set([
  "failed",
  "auth_required",
  "schedule_expired",
]);

export function canRetryPublish(video: PublishState): boolean {
  return (
    video.approval_status === "approved" &&
    RETRYABLE_PUBLISH_STATUSES.has(video.publish_status)
  );
}

export function canSubmitPublish(video: PublishState): boolean {
  return video.approval_status === "pending" || canRetryPublish(video);
}

export function needsPronunciationConfirmation(
  video: PronunciationState,
): boolean {
  return (
    video.pronunciation_review_required &&
    video.pronunciation_reviewed_at === null
  );
}
