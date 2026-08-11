from datetime import datetime
from zoneinfo import ZoneInfo

from app.frontend.video_view_state import (
    VideoViewKind,
    build_video_view_state,
    can_create_rush_hour_short,
    default_activation_at,
)


KST = ZoneInfo("Asia/Seoul")


def test_only_rush_hour_results_can_create_comic_short():
    assert can_create_rush_hour_short({"result_id": "res_1", "time_slot": "commute_am"}) is True
    assert can_create_rush_hour_short({"result_id": "res_2", "time_slot": "commute_pm"}) is True
    assert can_create_rush_hour_short({"result_id": "res_3", "time_slot": "afternoon"}) is False
    assert can_create_rush_hour_short({"time_slot": "commute_am"}) is False


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
