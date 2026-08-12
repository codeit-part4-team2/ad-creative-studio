from datetime import datetime
from zoneinfo import ZoneInfo

from app.backend.services.exposure import (
    get_current_time_slot,
    pick_exposure,
    pick_video_exposure,
)


def test_get_current_time_slot_morning():
    assert get_current_time_slot(datetime(2026, 8, 5, 7, 0)) == "morning"


def test_get_current_time_slot_commute_am():
    assert get_current_time_slot(datetime(2026, 8, 5, 8, 30)) == "commute_am"


def test_get_current_time_slot_afternoon():
    assert get_current_time_slot(datetime(2026, 8, 5, 14, 0)) == "afternoon"


def test_get_current_time_slot_commute_pm():
    assert get_current_time_slot(datetime(2026, 8, 5, 18, 45)) == "commute_pm"


def test_get_current_time_slot_evening():
    assert get_current_time_slot(datetime(2026, 8, 5, 20, 30)) == "evening"


def test_get_current_time_slot_late_night_before_midnight():
    assert get_current_time_slot(datetime(2026, 8, 5, 23, 0)) == "late_night"


def test_get_current_time_slot_late_night_after_midnight():
    assert get_current_time_slot(datetime(2026, 8, 5, 3, 0)) == "late_night"


def test_get_current_time_slot_covers_all_24_hours():
    """0~23시 전부 예외 없이 슬롯이 판정되는지."""
    for hour in range(24):
        slot = get_current_time_slot(datetime(2026, 8, 5, hour, 0))
        assert slot in {"morning", "commute_am", "afternoon", "commute_pm", "evening", "late_night"}


def test_utc_time_is_converted_to_kst():
    """서버가 UTC 등 다른 타임존이어도, KST 기준으로 판정돼야 한다."""
    utc_time = datetime(2026, 8, 5, 23, 30, tzinfo=ZoneInfo("UTC"))
    # KST는 UTC+9 → 다음 날 08:30 → 출근 러시아워
    assert get_current_time_slot(utc_time) == "commute_am"


def test_naive_datetime_is_treated_as_kst():
    """타임존 정보 없는 naive datetime은 이미 KST라고 가정하고 그대로 판정한다."""
    naive_time = datetime(2026, 8, 5, 8, 30)  # tzinfo 없음
    assert get_current_time_slot(naive_time) == "commute_am"


def test_pick_exposure_returns_matching_result():
    history = [
        {
            "product_id": "prd_1",
            "results": [
                {"tone": "emotional", "time_slot": "commute_am", "headline": "아침 특가"},
                {"tone": "modern", "time_slot": "evening", "headline": "저녁 룩"},
            ],
        }
    ]
    result = pick_exposure("prd_1", history, now=datetime(2026, 8, 5, 8, 30))
    assert result["available"] is True
    assert result["time_slot"] == "commute_am"
    assert len(result["tones"]) == 1
    assert result["tones"][0]["headline"] == "아침 특가"


def test_pick_exposure_returns_unavailable_when_no_match():
    history = [
        {"product_id": "prd_1", "results": [{"tone": "emotional", "time_slot": "evening"}]}
    ]
    result = pick_exposure("prd_1", history, now=datetime(2026, 8, 5, 8, 30))
    assert result["available"] is False
    assert result["tones"] is None


def test_pick_exposure_ignores_other_products():
    history = [
        {"product_id": "prd_OTHER", "results": [{"tone": "emotional", "time_slot": "commute_am"}]}
    ]
    result = pick_exposure("prd_1", history, now=datetime(2026, 8, 5, 8, 30))
    assert result["available"] is False


def _video_job(job_id, **overrides):
    values = {
        "video_job_id": job_id,
        "product_id": "prd_1",
        "time_slot": "commute_am",
        "render_status": "completed",
        "approval_status": "approved",
        "publish_status": "not_requested",
        "activation_at": "2026-08-10T08:00:00+09:00",
        "approved_at": "2026-08-09T12:00:00+09:00",
        "updated_at": "2026-08-09T12:00:00+09:00",
        "video_url": f"/files/videos/{job_id}.mp4",
    }
    values.update(overrides)
    return values


def test_pick_video_exposure_returns_latest_approved_active_video():
    jobs = {
        "older": _video_job(
            "older",
            approved_at="2026-08-08T12:00:00+09:00",
        ),
        "latest": _video_job(
            "latest",
            publish_status="failed",
            approved_at="2026-08-09T12:00:00+09:00",
        ),
    }

    response = pick_video_exposure(
        "prd_1",
        time_slot="commute_am",
        video_jobs=jobs,
        now=datetime(2026, 8, 10, 8, 30, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert response == {
        "video_job_id": "latest",
        "video_url": "/files/videos/latest.mp4",
    }


def test_pick_exposure_attaches_video_without_requiring_banner_history():
    jobs = {"video_1": _video_job("video_1")}

    response = pick_exposure(
        "prd_1",
        history=[],
        video_jobs=jobs,
        now=datetime(2026, 8, 10, 8, 30),
    )

    assert response["available"] is False
    assert response["video"]["video_job_id"] == "video_1"


def test_non_rush_hour_never_returns_video():
    response = pick_exposure(
        "prd_1",
        history=[],
        video_jobs={"video_1": _video_job("video_1")},
        now=datetime(2026, 8, 10, 14, 0),
    )

    assert response["video"] is None


def test_ineligible_video_jobs_are_ignored():
    cases = [
        {"approval_status": "pending"},
        {"approval_status": "rejected"},
        {"render_status": "processing"},
        {"activation_at": "2026-08-10T08:31:00+09:00"},
        {"product_id": "prd_other"},
        {"time_slot": "commute_pm"},
        {"video_url": None},
        {"activation_at": "not-a-date"},
    ]
    now = datetime(2026, 8, 10, 8, 30, tzinfo=ZoneInfo("Asia/Seoul"))

    for index, overrides in enumerate(cases):
        result = pick_video_exposure(
            "prd_1",
            time_slot="commute_am",
            video_jobs={"job": _video_job(f"job_{index}", **overrides)},
            now=now,
        )
        assert result is None
