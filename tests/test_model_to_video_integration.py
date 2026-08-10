from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.backend.schemas.video import RenderStatus
from app.backend.services import store
from app.backend.services.video_workflow import VideoWorkflowService
from app.backend.services.youtube_publisher import DisabledPublisher


class _RecordingRenderer:
    def __init__(self) -> None:
        self.image_paths: list[Path] = []

    def render(self, storyboard, *, output_path: Path, music_path: Path | None):
        self.image_paths.append(storyboard.image_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"model-result-short")
        return SimpleNamespace(
            output_path=output_path,
            sha256="2d3b97f59f6a5f7a17f1be55c654a6d3f08cf53161de253913247674f37b96f6",
            music_warning="music_unavailable",
        )


def test_persisted_model_result_renders_as_rush_hour_short(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "var" / "store.json")
    store.PRODUCTS.clear()
    store.HISTORY.clear()
    store.VIDEO_JOBS.clear()

    output_path = tmp_path / "data" / "outputs" / "model-card.png"
    output_path.parent.mkdir(parents=True)
    Image.new("RGB", (1024, 1024), "navy").save(output_path)
    store.PRODUCTS["prd_model"] = {
        "product_name": "휴대용 선풍기",
        "selling_points": ["USB-C 충전", "저소음"],
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

    renderer = _RecordingRenderer()
    workflow = VideoWorkflowService(
        renderer=renderer,
        music_catalog=None,
        publisher=DisabledPublisher("test_channel"),
        now=lambda: datetime(2026, 8, 10, tzinfo=timezone.utc),
        video_dir=tmp_path / "data" / "videos",
    )

    job = workflow.create("res_model")
    workflow.run_render(job.video_job_id)

    completed = workflow.get(job.video_job_id)
    assert completed.render_status is RenderStatus.COMPLETED
    assert renderer.image_paths == [output_path.resolve()]
    assert completed.video_url == f"/files/videos/{job.video_job_id}.mp4"
