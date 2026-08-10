from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.backend.schemas.video import (
    ApprovalStatus,
    PublishStatus,
    RenderStatus,
    VideoJob,
)
from app.backend.services import store


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.PRODUCTS.clear()
    store.JOBS.clear()
    store.HISTORY.clear()
    store.VIDEO_JOBS.clear()
    yield
    store.PRODUCTS.clear()
    store.JOBS.clear()
    store.HISTORY.clear()
    store.VIDEO_JOBS.clear()


def _job(**overrides) -> VideoJob:
    now = datetime(2026, 8, 8, 18, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    values = {
        "video_job_id": "video_1",
        "result_id": "res_1",
        "product_id": "prd_1",
        "tone": "practical",
        "time_slot": "commute_am",
        "render_status": RenderStatus.COMPLETED,
        "approval_status": ApprovalStatus.APPROVED,
        "publish_status": PublishStatus.SCHEDULED,
        "video_url": "/files/videos/video_1.mp4",
        "video_sha256": "a" * 64,
        "source_fingerprint": "b" * 64,
        "activation_at": datetime(2026, 8, 10, 8, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        "approved_at": now,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return VideoJob(**values)


def test_video_jobs_round_trip_as_json_safe_data():
    job = _job()
    store.VIDEO_JOBS[job.video_job_id] = job.model_dump(mode="json")

    store.save()
    store.VIDEO_JOBS.clear()
    store.load()

    restored = VideoJob.model_validate(store.VIDEO_JOBS["video_1"])
    assert restored.publish_status is PublishStatus.SCHEDULED
    assert restored.activation_at == datetime(
        2026, 8, 10, 8, 0, tzinfo=ZoneInfo("Asia/Seoul")
    )


def test_interrupted_video_jobs_are_recovered_without_duplicate_work():
    rendering = _job(
        video_job_id="rendering",
        render_status=RenderStatus.PROCESSING,
        approval_status=ApprovalStatus.PENDING,
        publish_status=PublishStatus.NOT_REQUESTED,
        video_url=None,
        video_sha256=None,
        activation_at=None,
        approved_at=None,
    )
    uploading = _job(
        video_job_id="uploading",
        publish_status=PublishStatus.PENDING,
        youtube_video_id=None,
    )
    store.VIDEO_JOBS.update(
        {
            rendering.video_job_id: rendering.model_dump(mode="json"),
            uploading.video_job_id: uploading.model_dump(mode="json"),
        }
    )
    store.save()
    store.VIDEO_JOBS.clear()

    store.load()

    recovered_render = VideoJob.model_validate(store.VIDEO_JOBS["rendering"])
    recovered_upload = VideoJob.model_validate(store.VIDEO_JOBS["uploading"])
    assert recovered_render.render_status is RenderStatus.FAILED
    assert "서버 재시작" in (recovered_render.error_message or "")
    assert recovered_upload.publish_status is PublishStatus.NEEDS_REVIEW
    assert "확인" in (recovered_upload.youtube_error or "")


def test_reset_for_tests_clears_video_jobs():
    job = _job()
    store.VIDEO_JOBS[job.video_job_id] = job.model_dump(mode="json")
    store.save()

    store.reset_for_tests()

    assert store.VIDEO_JOBS == {}
    assert not store.STORE_PATH.exists()
