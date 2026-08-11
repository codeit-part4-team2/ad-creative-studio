import hashlib
import wave
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.backend.api import videos, youtube
from app.backend.services import store
from app.backend.services.comic_script import ComicLineKind
from app.backend.services.scene_images import SceneImage, SceneImageSet
from app.backend.services.storyboard import Storyboard, StoryboardNotFound, StoryboardScene
from app.backend.services.tts_provider import TTSAudio
from app.backend.services.video_renderer import RenderResult
from app.backend.services.video_workflow import VideoWorkflowService
from app.backend.services.youtube_publisher import PublisherStatus


KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=KST)
ACTIVATION = "2026-08-10T08:00:00+09:00"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ApiSceneProvider:
    def build(self, *, storyboard, product_image_url, output_dir):
        images = []
        for purpose, color in (("hero", "navy"), ("self_aware", "red"), ("benefit", "green")):
            path = output_dir / f"{purpose}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), color).save(path)
            images.append(SceneImage(purpose, path.resolve(), _sha256(path), "api-test"))
        return SceneImageSet(images=tuple(images))


class ApiTTSProvider:
    def synthesize(self, spoken_text, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8_000)
            wav_file.writeframes(b"\x00\x00" * 800)
        return TTSAudio(
            output_path.resolve(),
            0.1,
            _sha256(output_path),
            "melotts-korean",
            "deadpan-ai-v1",
        )


class ApiRenderer:
    def render(self, storyboard, *, scene_images, speech_audio, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"api-video")
        return RenderResult(
            output_path=output_path.resolve(),
            sha256=_sha256(output_path),
            duration_sec=12.5,
            width=1080,
            height=1920,
            video_codec="h264",
            audio_codec="aac",
            tts_audio_sha256=hashlib.sha256(b"api-tts").hexdigest(),
            scene_image_sha256s=scene_images.sha256s,
            caption_layout_version="bright-outline-v1",
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
    Image.new("RGB", (16, 16), "navy").save(image_path)
    scenes = (
        StoryboardScene("휴대용 선풍기입니다.", 2.0, kind=ComicLineKind.INTRO),
        StoryboardScene("저는 시간을 느끼지 못합니다.", 2.0, kind=ComicLineKind.SELF_AWARE),
        StoryboardScene("장점은 저소음입니다.", 2.0, kind=ComicLineKind.BENEFIT),
        StoryboardScene("출근 전에 확인해 보세요.", 2.0, kind=ComicLineKind.CTA),
    )

    def storyboard_builder(result_id):
        if result_id == "res_missing":
            raise StoryboardNotFound("result_id에 해당하는 생성 결과가 없습니다")
        if result_id == "res_afternoon":
            raise ValueError("러시아워 결과만 지원합니다")
        return Storyboard(
            result_id=result_id,
            product_id="prd_1",
            tone="practical",
            time_slot="commute_am",
            product_name="휴대용 선풍기",
            image_path=image_path,
            scenes=scenes,
            source_fingerprint="a" * 64,
            script_version="deadpan-ai-v1",
        )

    publisher = ApiPublisher()
    workflow = VideoWorkflowService(
        renderer=ApiRenderer(),
        scene_image_provider=ApiSceneProvider(),
        tts_provider=ApiTTSProvider(),
        publisher=publisher,
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        work_dir=tmp_path / "work",
        storyboard_builder=storyboard_builder,
        fingerprint_builder=lambda _: "a" * 64,
        product_image_url_builder=lambda _: "/files/uploads/prd_1.png",
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
    assert client.post("/api/v1/videos", json={"result_id": "res_missing"}).status_code == 404
    assert client.post("/api/v1/videos", json={"result_id": "res_afternoon"}).status_code == 400


def test_get_unknown_job_returns_404(api):
    client, _, _ = api
    assert client.get("/api/v1/videos/video_missing").status_code == 404


def test_approve_returns_pending_contract_and_background_schedules(api):
    client, workflow, publisher = api
    job_id = _create_completed(api)
    response = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={"activation_at": ACTIVATION, "publish_to_youtube": True},
    )
    assert response.status_code == 202
    assert response.json()["approval_status"] == "approved"
    assert response.json()["publish_status"] == "pending"
    assert workflow.get(job_id).publish_status == "scheduled"
    assert len(publisher.requests) == 1


def test_removed_allow_silent_field_is_rejected(api):
    client, _, _ = api
    job_id = _create_completed(api)
    response = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={
            "activation_at": ACTIVATION,
            "publish_to_youtube": False,
            "allow_silent": True,
        },
    )
    assert response.status_code == 422


def test_pronunciation_review_requires_explicit_listening_confirmation(api):
    client, workflow, _ = api
    job_id = _create_completed(api)
    store.VIDEO_JOBS[job_id]["pronunciation_review_required"] = True

    blocked = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={"activation_at": ACTIVATION, "publish_to_youtube": False},
    )
    assert blocked.status_code == 409

    approved = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={
            "activation_at": ACTIVATION,
            "publish_to_youtube": False,
            "pronunciation_confirmed": True,
        },
    )
    assert approved.status_code == 202
    assert workflow.get(job_id).pronunciation_reviewed_at is not None


def test_invalid_lead_time_returns_422(api):
    client, _, _ = api
    job_id = _create_completed(api)
    response = client.post(
        f"/api/v1/videos/{job_id}/approve",
        json={"activation_at": "2026-08-08T12:05:00+09:00", "publish_to_youtube": False},
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
    assert "token_file" not in response.text.lower()


def test_internal_exception_is_sanitized(api, monkeypatch):
    client, workflow, _ = api

    def fail(_):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(workflow, "create", fail)
    response = client.post("/api/v1/videos", json={"result_id": "res_ok"})
    assert response.status_code == 500
    assert "secret internal detail" not in response.text
