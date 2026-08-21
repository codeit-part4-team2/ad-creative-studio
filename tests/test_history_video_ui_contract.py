from datetime import datetime
from zoneinfo import ZoneInfo

from app.frontend import video_view_state
from app.frontend.video_view_state import (
    VideoViewKind,
    build_video_view_state,
    can_create_rush_hour_short,
    default_activation_at,
    short_creation_unavailable_reason,
)


KST = ZoneInfo("Asia/Seoul")


def test_short_creation_eligibility_distinguishes_ready_legacy_and_daytime():
    eligible = video_view_state.rush_hour_short_eligibility(
        {
            "result_id": "res_ready",
            "time_slot": "commute_am",
            "source_image_url": "/files/outputs/source.png",
        }
    )
    legacy = video_view_state.rush_hour_short_eligibility(
        {"result_id": "res_legacy", "time_slot": "commute_pm"}
    )
    daytime = video_view_state.rush_hour_short_eligibility(
        {"result_id": "res_day", "time_slot": "afternoon"}
    )

    assert (eligible.can_create, eligible.unavailable_reason) == (True, None)
    assert (legacy.can_create, legacy.unavailable_reason) == (
        False,
        "이 결과에는 쇼츠용 무자막 원본이 없습니다. 광고를 다시 생성해 주세요.",
    )
    assert (daytime.can_create, daytime.unavailable_reason) == (False, None)


def test_only_rush_hour_results_can_create_comic_short():
    assert can_create_rush_hour_short(
        {
            "result_id": "res_1",
            "time_slot": "commute_am",
            "source_image_url": "/files/outputs/source-1.png",
        }
    ) is True
    assert can_create_rush_hour_short(
        {
            "result_id": "res_2",
            "time_slot": "commute_pm",
            "source_image_url": "/files/outputs/source-2.png",
        }
    ) is True
    assert can_create_rush_hour_short({"result_id": "res_3", "time_slot": "afternoon"}) is False
    assert can_create_rush_hour_short({"time_slot": "commute_am"}) is False


def test_legacy_rush_hour_result_requires_ad_regeneration():
    legacy_result = {"result_id": "res_legacy", "time_slot": "commute_am"}

    assert can_create_rush_hour_short(legacy_result) is False
    assert short_creation_unavailable_reason(legacy_result) == (
        "이 결과에는 쇼츠용 무자막 원본이 없습니다. 광고를 다시 생성해 주세요."
    )
    assert short_creation_unavailable_reason(
        {"result_id": "res_day", "time_slot": "afternoon"}
    ) is None


def test_view_state_blocks_approval_until_pronunciation_is_reviewed():
    state = build_video_view_state(
        {
            "render_status": "completed",
            "approval_status": "pending",
            "publish_status": "not_requested",
            "video_url": "/files/videos/video_1.mp4",
            "pronunciation_review_required": True,
        }
    )

    assert state.kind is VideoViewKind.PRONUNCIATION_REVIEW
    assert state.show_video is True
    assert state.can_approve is False
    assert state.can_confirm_pronunciation is True


def test_completed_video_exposes_explicit_approve_and_reject_actions():
    state = build_video_view_state(
        {
            "render_status": "completed",
            "approval_status": "pending",
            "publish_status": "not_requested",
            "video_url": "/files/videos/video_1.mp4",
            "pronunciation_review_required": False,
        }
    )

    assert state.kind is VideoViewKind.REVIEW
    assert state.can_approve is True
    assert state.can_reject is True


def test_approved_and_publishing_states_are_distinct():
    approved = build_video_view_state(
        {
            "render_status": "completed",
            "approval_status": "approved",
            "publish_status": "not_requested",
            "video_url": "/files/videos/video_1.mp4",
        }
    )
    publishing = build_video_view_state(
        {
            "render_status": "completed",
            "approval_status": "approved",
            "publish_status": "pending",
            "video_url": "/files/videos/video_1.mp4",
        }
    )

    assert approved.kind is VideoViewKind.APPROVED
    assert publishing.kind is VideoViewKind.PUBLISHING


def test_default_activation_uses_next_valid_rush_hour():
    now = datetime(2026, 8, 11, 8, 55, tzinfo=KST)

    activation = default_activation_at("commute_am", now)

    assert activation == datetime(2026, 8, 12, 8, 0, tzinfo=KST)
