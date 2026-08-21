from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from app.media_urls import normalize_optional_url
from app.time_slots import is_rush_hour_slot

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


@dataclass(frozen=True, slots=True)
class ShortCreationEligibility:
    can_create: bool
    unavailable_reason: str | None = None


def rush_hour_short_eligibility(
    result: dict[str, object],
) -> ShortCreationEligibility:
    if not bool(result.get("result_id")) or not is_rush_hour_slot(
        result.get("time_slot")
    ):
        return ShortCreationEligibility(can_create=False)

    source_image_url = normalize_optional_url(result.get("source_image_url"))
    if isinstance(source_image_url, str) and source_image_url.startswith(
        "/files/outputs/"
    ):
        return ShortCreationEligibility(can_create=True)
    return ShortCreationEligibility(
        can_create=False,
        unavailable_reason=(
            "이 결과에는 쇼츠용 무자막 원본이 없습니다. "
            "광고를 다시 생성해 주세요."
        ),
    )


def can_create_rush_hour_short(result: dict[str, object]) -> bool:
    return rush_hour_short_eligibility(result).can_create


def short_creation_unavailable_reason(
    result: dict[str, object],
) -> str | None:
    return rush_hour_short_eligibility(result).unavailable_reason


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
