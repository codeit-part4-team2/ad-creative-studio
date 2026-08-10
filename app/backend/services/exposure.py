from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.prompt.templates import TIME_SLOT_TEMPLATES


KST = ZoneInfo("Asia/Seoul")


def _as_kst(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(KST)
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def get_current_time_slot(now: Optional[datetime] = None) -> str:
    """Return the configured time slot using Asia/Seoul as the authority."""
    local_now = _as_kst(now)
    hour_float = local_now.hour + local_now.minute / 60

    for slot, info in TIME_SLOT_TEMPLATES.items():
        start, end = info["hour_range"]
        if start < end:
            if start <= hour_float < end:
                return slot
        elif hour_float >= start or hour_float < end:
            return slot

    raise RuntimeError("시간대 판정 실패 - TIME_SLOT_TEMPLATES를 확인하세요")


def _aware_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(KST)


def pick_video_exposure(
    product_id: str,
    *,
    time_slot: str,
    video_jobs: dict[str, dict],
    now: datetime,
) -> dict | None:
    """Select the latest eligible approved video independently of YouTube."""
    if time_slot not in {"commute_am", "commute_pm"}:
        return None

    local_now = _as_kst(now)
    candidates: list[tuple[datetime, datetime, dict]] = []
    earliest = datetime.min.replace(tzinfo=KST)
    for job in video_jobs.values():
        activation_at = _aware_datetime(job.get("activation_at"))
        if (
            job.get("product_id") != product_id
            or job.get("time_slot") != time_slot
            or job.get("render_status") != "completed"
            or job.get("approval_status") != "approved"
            or not job.get("video_url")
            or activation_at is None
            or activation_at > local_now
        ):
            continue
        approved_at = _aware_datetime(job.get("approved_at")) or earliest
        updated_at = _aware_datetime(job.get("updated_at")) or earliest
        candidates.append((approved_at, updated_at, job))

    if not candidates:
        return None
    selected = max(candidates, key=lambda candidate: candidate[:2])[2]
    return {
        "video_job_id": selected["video_job_id"],
        "video_url": selected["video_url"],
    }


def pick_exposure(
    product_id: str,
    history: list[dict],
    now: Optional[datetime] = None,
    *,
    video_jobs: dict[str, dict] | None = None,
) -> dict:
    """Return the current banner exposure plus any eligible approved video."""
    local_now = _as_kst(now)
    current_slot = get_current_time_slot(local_now)
    slot_label = TIME_SLOT_TEMPLATES[current_slot]["label"]
    video = pick_video_exposure(
        product_id,
        time_slot=current_slot,
        video_jobs=video_jobs or {},
        now=local_now,
    )

    for entry in reversed(history):
        if entry.get("product_id") != product_id:
            continue
        matching_tones = [
            result
            for result in entry.get("results", [])
            if result.get("time_slot") == current_slot
        ]
        if matching_tones:
            return {
                "time_slot": current_slot,
                "time_slot_label": slot_label,
                "available": True,
                "tones": matching_tones,
                "video": video,
            }

    return {
        "time_slot": current_slot,
        "time_slot_label": slot_label,
        "available": False,
        "tones": None,
        "video": video,
    }
