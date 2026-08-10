from pathlib import Path


HISTORY_PAGE = Path("app/frontend/pages/3_History.py")


def test_history_page_contains_video_approval_contract():
    source = HISTORY_PAGE.read_text(encoding="utf-8")

    assert "def default_activation_at" in source
    assert "def render_video_workflow" in source
    assert "/approve" in source
    assert "/reject" in source
    assert "publish_to_youtube" in source
    assert "allow_silent" in source
    assert "activation_at" in source
    assert "승인 전에는 게시되지 않습니다" in source


def test_history_page_uses_separate_render_approval_and_publish_states():
    source = HISTORY_PAGE.read_text(encoding="utf-8")

    assert "render_status" in source
    assert "approval_status" in source
    assert "publish_status" in source
    assert "music_warning" in source
    assert "/api/v1/youtube/status" in source
    assert "connection_id" in source
    assert "token_file" not in source
    assert "client_secret" not in source


def test_history_page_limits_video_creation_to_rush_hour_results():
    source = HISTORY_PAGE.read_text(encoding="utf-8")

    assert 'RUSH_HOUR_SLOTS = {"commute_am", "commute_pm"}' in source
    assert 'result.get("time_slot") not in RUSH_HOUR_SLOTS' in source
    assert "st.video" in source
