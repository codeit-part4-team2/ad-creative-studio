import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.backend.api import videos, youtube
from app.backend.services import store
from app.backend.services.storyboard import (
    Storyboard,
    StoryboardNotFound,
    StoryboardScene,
)
from app.backend.services.video_renderer import RenderResult
from app.backend.services.video_workflow import VideoWorkflowService
from app.backend.services.youtube_publisher import PublisherStatus


KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=KST)
ACTIVATION = "2026-08-10T08:00:00+09:00"


class ApiRenderer:
    def render(self, storyboard, *, output_path, music_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"api-video")
        return RenderResult(
            output_path=output_path,
            sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            duration_sec=12.5,
            width=1080,
            height=1920,
            video_codec="h264",
            audio_codec="aac",
            music_warning="music_unavailable",
        )


class ApiPublisher:
    def __init__(self):
        self.requests = []

    def status(self):
        return PublisherStatus(True, "demo_merchant_channel", True)

    def publish(self, request):
        self.requests.append(request)
        return "youtube_api_123"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.reset_for_tests()
    image_path = tmp_path / "source.png"
    image_path.write_bytes(b"source")
    board = Storyboard(
        result_id="res_ok",
        product_id="prd_1",
        tone="practical",
        time_slot="commute_am",
        product_name="휴대용 선풍기",
        image_path=image_path,
        scenes=(
            StoryboardScene("출근길 필수템", 5.0),
            StoryboardScene("가볍고 시원하게", 5.0),
        ),
        source_fingerprint="a" * 64,
    )

    def storyboard_builder(result_id):
        if result_id == "res_missing":
            raise StoryboardNotFound("result_id에 해당하는 생성 결과가 없습니다")
        if result_id == "res_afternoon":
            raise ValueError("러시아워 결과만 지원합니다")
        return board

    publisher = ApiPublisher()
    workflow = VideoWorkflowService(
        renderer=ApiRenderer(),
        music_catalog=None,
        publisher=publisher,
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        storyboard_builder=storyboard_builder,
        fingerprint_builder=lambda _: board.source_fingerprint,
    )
    app = FastAPI()
    app.state.video_workflow = workflow
    app.include_router(videos.router)
    app.include_router(youtube.router)
    client = TestClient(app, raise_server_exceptions=False)
    yield client, workflow, publisher
    store.reset_for_tests()


def _create_completed(api):
    client, workflow, _ = api
    response = client.post("/api/v1/videos", json={"result_id": "res_ok"})
    job_id = response.json()["video_job_id"]
    assert workflow.get(job_id).render_status == "completed"
    return job_id


def test_create_video_returns_202_queued_contract(api):
    client, _, _ = api

    response = client.post("/api/v1/videos", json={"result_id": "res_ok"})

    assert response.status_code == 202
    assert response.json()["render_status"] == "queued"
    assert response.json()["video_job_id"].startswith("video_")


def test_create_maps_unknown_and_non_rush_hour(api):
    client, _, _ = api

    missing = client.post("/api/v1/videos", json={"result_id": "res_missing"})
    afternoon = client.post("/api/v1/videos", json={"result_id": "res_afternoon"})

    assert missing.status_code == 404
    assert afternoon.status_code == 400


def test_get_unknown_job_returns_404(api):
    client, _, _ = api

    response = client.get("/api/v1/videos/video_missing")

    assert response.status_code == 404


def test_approve_returns_202_pending_contract_and_background_schedules(api):
    client, workflow, publisher = api
    job_id = _create_completed(api)

    response = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={
            "activation_at": ACTIVATION,
            "publish_to_youtube": True,
            "allow_silent": True,
        },
    )

    assert response.status_code == 202
    assert response.json()["approval_status"] == "approved"
    assert response.json()["publish_status"] == "pending"
    assert workflow.get(job_id).publish_status == "scheduled"
    assert len(publisher.requests) == 1


def test_silent_confirmation_conflict_returns_409(api):
    client, _, _ = api
    job_id = _create_completed(api)

    response = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={
            "activation_at": ACTIVATION,
            "publish_to_youtube": False,
            "allow_silent": False,
        },
    )

    assert response.status_code == 409


def test_invalid_lead_time_returns_422(api):
    client, _, _ = api
    job_id = _create_completed(api)

    response = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={
            "activation_at": "2026-08-08T12:05:00+09:00",
            "publish_to_youtube": False,
            "allow_silent": True,
        },
    )

    assert response.status_code == 422


def test_reject_endpoint_is_persisted(api):
    client, _, _ = api
    job_id = _create_completed(api)

    response = client.post(f"/api/v1/videos/{job_id}/reject")

    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"


def test_youtube_status_has_only_safe_fields(api):
    client, _, _ = api

    response = client.get("/api/v1/youtube/status")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "connection_id": "demo_merchant_channel",
        "token_available": True,
    }
    assert "path" not in response.text.lower()
    assert "token_file" not in response.text.lower()


def test_internal_exception_is_sanitized(api, monkeypatch):
    client, workflow, _ = api

    def fail(_):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(workflow, "create", fail)
    response = client.post("/api/v1/videos", json={"result_id": "res_ok"})

    assert response.status_code == 500
    assert "secret internal detail" not in response.text
