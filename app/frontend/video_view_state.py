from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


RUSH_HOUR_SLOTS = {"commute_am", "commute_pm"}
KST = ZoneInfo("Asia/Seoul")


class VideoViewKind(str, Enum):
    CREATING = "creating"
    FAILED = "failed"
    PRONUNCIATION_REVIEW = "pronunciation_review"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISH_WARNING = "publish_warning"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class VideoViewState:
    kind: VideoViewKind
    show_video: bool
    can_approve: bool = False
    can_reject: bool = False
    can_confirm_pronunciation: bool = False


def can_create_rush_hour_short(result: dict[str, object]) -> bool:
    return bool(result.get("result_id")) and result.get("time_slot") in RUSH_HOUR_SLOTS


def default_activation_at(time_slot: str, now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        kst_now = now.replace(tzinfo=KST)
    else:
        kst_now = now.astimezone(KST)
    target_time = time(8, 0) if time_slot == "commute_am" else time(18, 0)
    candidate = datetime.combine(kst_now.date(), target_time, tzinfo=KST)
    if candidate < kst_now + timedelta(minutes=10):
        candidate += timedelta(days=1)
    return candidate


def build_video_view_state(job: dict[str, object]) -> VideoViewState:
    render_status = job.get("render_status")
    approval_status = job.get("approval_status")
    publish_status = job.get("publish_status")
    show_video = bool(job.get("video_url")) and render_status == "completed"
    if render_status in {"queued", "processing"}:
        return VideoViewState(VideoViewKind.CREATING, show_video=False)
    if render_status == "failed":
        return VideoViewState(VideoViewKind.FAILED, show_video=False)
    if approval_status == "rejected":
        return VideoViewState(VideoViewKind.REJECTED, show_video=show_video)
    if approval_status == "approved":
        if publish_status == "pending":
            return VideoViewState(VideoViewKind.PUBLISHING, show_video=show_video)
        if publish_status not in {None, "not_requested", "scheduled"}:
            return VideoViewState(VideoViewKind.PUBLISH_WARNING, show_video=show_video)
        return VideoViewState(VideoViewKind.APPROVED, show_video=show_video)
    if job.get("pronunciation_review_required"):
        return VideoViewState(
            VideoViewKind.PRONUNCIATION_REVIEW,
            show_video=show_video,
            can_reject=True,
            can_confirm_pronunciation=True,
        )
    return VideoViewState(
        VideoViewKind.REVIEW,
        show_video=show_video,
        can_approve=True,
        can_reject=True,
    )
