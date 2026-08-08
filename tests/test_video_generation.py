import asyncio

import pytest

from app.backend.services import video_generation_service as vgs
from app.backend.services.store import HISTORY, PRODUCTS


@pytest.fixture(autouse=True)
def _clear(tmp_path, monkeypatch):
    monkeypatch.setattr(vgs, "VIDEO_DIR", tmp_path / "videos")  # 실제 data/videos/ 안 건드림
    HISTORY.clear()
    PRODUCTS.clear()
    yield
    HISTORY.clear()
    PRODUCTS.clear()


def _seed_history(time_slot="commute_am", with_selling_points=True):
    PRODUCTS["prd_1"] = {
        "product_name": "휴대용 선풍기",
        "selling_points": ["USB-C 충전", "8시간 사용"] if with_selling_points else [],
    }
    HISTORY.append({
        "job_id": "job_1",
        "product_id": "prd_1",
        "results": [{
            "result_id": "res_abc123",
            "tone": "practical",
            "time_slot": time_slot,
            "headline": "출근길 필수템",
            "subcopy": "가볍고 시원하게",
            "images": {"thumbnail": "/files/outputs/job_1_practical_commute_am_thumbnail_x.png"},
        }],
        "favorite": False,
    })


def test_find_tone_result_returns_matching_entry():
    _seed_history()
    entry, tone_result = vgs.find_tone_result("res_abc123")
    assert entry["job_id"] == "job_1"
    assert tone_result["headline"] == "출근길 필수템"


def test_find_tone_result_returns_none_for_unknown_id():
    _seed_history()
    entry, tone_result = vgs.find_tone_result("res_doesnotexist")
    assert entry is None
    assert tone_result is None


def test_build_scenes_includes_headline_scene():
    _seed_history()
    scenes = vgs.build_scenes_from_result("res_abc123")
    assert scenes[0]["text"] == "출근길 필수템"
    assert scenes[0]["image_path"] == "data/outputs/job_1_practical_commute_am_thumbnail_x.png"


def test_build_scenes_adds_selling_points_scene_when_present():
    _seed_history(with_selling_points=True)
    scenes = vgs.build_scenes_from_result("res_abc123")
    assert len(scenes) == 2
    assert "USB-C 충전" in scenes[1]["narration"]


def test_build_scenes_skips_selling_points_scene_when_absent():
    _seed_history(with_selling_points=False)
    scenes = vgs.build_scenes_from_result("res_abc123")
    assert len(scenes) == 1


def test_build_scenes_raises_for_unknown_result_id():
    _seed_history()
    with pytest.raises(ValueError):
        vgs.build_scenes_from_result("res_nope")


def test_mock_service_create_rejects_non_rush_hour_slot():
    """time_slot을 안 받고, result_id로 찾은 실제 결과의 시간대로 판정해야 한다."""
    _seed_history(time_slot="afternoon")
    mock = vgs.MockVideoGenerationService()
    result = asyncio.run(mock.create("res_abc123"))
    assert result.status == "failed"
    assert "출근/퇴근" in result.error_message


def test_mock_service_create_succeeds_for_rush_hour_slot():
    _seed_history(time_slot="commute_am")
    mock = vgs.MockVideoGenerationService()
    result = asyncio.run(mock.create("res_abc123"))
    assert result.status == "queued"
    assert result.job_id.startswith("video_mock_")


def test_mock_service_create_fails_for_unknown_result_id():
    mock = vgs.MockVideoGenerationService()
    result = asyncio.run(mock.create("res_nope"))
    assert result.status == "failed"


def test_mock_service_get_status_returns_completed_with_url():
    mock = vgs.MockVideoGenerationService()
    result = asyncio.run(mock.get_status("video_mock_abc123"))
    assert result.status == "completed"
    assert result.video_url == "/files/videos/mock_short.mp4"


def test_frontend_rush_hour_slots_constant_matches_backend():
    """
    3_History.py는 streamlit run 환경 문제로 백엔드 상수를 import 못 하고 로컬에
    하드코딩된 값을 쓴다 (의도된 결정). 두 값이 어긋나면 백엔드가 조용히 400만 던지고
    프론트는 원인 모른 채 버튼만 눈에 보이는 상태가 되므로, 소스 텍스트를 직접 읽어
    두 상수가 항상 같은 값인지 회귀 테스트로 잡는다.
    """
    import re
    from pathlib import Path

    history_path = Path(__file__).parent.parent / "app" / "frontend" / "pages" / "3_History.py"
    source = history_path.read_text(encoding="utf-8")
    match = re.search(r'RUSH_HOUR_SLOTS\s*=\s*\{([^}]*)\}', source)
    assert match, "3_History.py에서 RUSH_HOUR_SLOTS 정의를 못 찾음 (삭제/이름변경됐다면 이 테스트도 갱신 필요)"

    frontend_values = {v.strip().strip('"').strip("'") for v in match.group(1).split(",") if v.strip()}
    assert frontend_values == vgs.RUSH_HOUR_SLOTS
