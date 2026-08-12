import hashlib
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from app.backend.schemas.video import RenderStatus
from app.backend.services import store
from app.backend.services.scene_images import SceneImageProvider
from app.backend.services.tts_provider import TTSAudio
from app.backend.services.video_renderer import RenderResult
from app.backend.services.video_workflow import VideoWorkflowService
from app.backend.services.youtube_publisher import DisabledPublisher


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _RecordingTTSProvider:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def synthesize(self, spoken_text: str, output_path: Path) -> TTSAudio:
        self.texts.append(spoken_text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(spoken_text.encode("utf-8"))
        return TTSAudio(
            path=output_path.resolve(),
            duration_sec=1.0,
            sha256=_sha256(output_path),
            engine="melotts-korean",
            voice_preset="deadpan-ai-v1",
        )


class _RecordingRenderer:
    def __init__(self) -> None:
        self.scene_count = 0
        self.audio_count = 0

    def render(self, storyboard, *, scene_images, speech_audio, output_path):
        self.scene_count = len(scene_images.images)
        self.audio_count = len(speech_audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"model-result-comic-short")
        return RenderResult(
            output_path=output_path.resolve(),
            sha256=_sha256(output_path),
            duration_sec=12.0,
            width=1080,
            height=1920,
            video_codec="h264",
            audio_codec="aac",
            tts_audio_sha256=hashlib.sha256(b"tts-audio-set").hexdigest(),
            scene_image_sha256s=scene_images.sha256s,
            caption_layout_version="bright-outline-v1",
        )


def test_persisted_model_result_builds_three_image_four_voice_short(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "var" / "store.json")
    store.reset_for_tests()
    hero_path = tmp_path / "data" / "outputs" / "model-card.png"
    hero_path.parent.mkdir(parents=True)
    Image.new("RGB", (1024, 1024), "navy").save(hero_path)
    store.PRODUCTS["prd_model"] = {
        "product_name": "휴대용 선풍기",
        "selling_points": ["저소음", "USB-C 충전"],
        "image_url": "/files/uploads/prd_model.png",
    }
    store.HISTORY.append(
        {
            "job_id": "job_model",
            "product_id": "prd_model",
            "results": [
                {
                    "result_id": "res_model",
                    "tone": "practical",
                    "time_slot": "commute_am",
                    "headline": "출근길 시원하게",
                    "subcopy": "가볍게 챙기세요",
                    "images": {"sns_card": "/files/outputs/model-card.png"},
                }
            ],
        }
    )
    requests: list[dict[str, object]] = []

    def request_generation(**kwargs):
        requests.append(kwargs)
        return {
            "status": "done",
            "generated_image_url": f"/files/outputs/short-scene-{len(requests)}.png",
            "product_preserved": True,
        }

    colors = iter(("red", "green"))
    scene_provider = SceneImageProvider(
        request_generation=request_generation,
        fetch_generated_image=lambda _url: Image.new("RGB", (1024, 1024), next(colors)),
    )
    tts_provider = _RecordingTTSProvider()
    renderer = _RecordingRenderer()
    workflow = VideoWorkflowService(
        renderer=renderer,
        scene_image_provider=scene_provider,
        tts_provider=tts_provider,
        publisher=DisabledPublisher("test_channel"),
        now=lambda: datetime(2026, 8, 10, tzinfo=timezone.utc),
        video_dir=tmp_path / "data" / "videos",
        work_dir=tmp_path / "var" / "video-work",
    )

    job = workflow.create("res_model")
    workflow.run_render(job.video_job_id)

    completed = workflow.get(job.video_job_id)
    assert completed.render_status is RenderStatus.COMPLETED
    assert len(requests) == 2
    assert all(request["product_image_url"] == "/files/uploads/prd_model.png" for request in requests)
    assert renderer.scene_count == 3
    assert renderer.audio_count == 4
    assert len(tts_provider.texts) == 4
    assert len(completed.scene_image_sha256s) == 3
    assert completed.video_url == f"/files/videos/{job.video_job_id}.mp4"
