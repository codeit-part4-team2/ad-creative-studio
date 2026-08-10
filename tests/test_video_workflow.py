import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.backend.schemas.video import ApprovalStatus, PublishStatus, RenderStatus
from app.backend.services import store
from app.backend.services.storyboard import (
    Storyboard,
    StoryboardNotFound,
    StoryboardScene,
)
from app.backend.services.video_renderer import RenderResult
from app.backend.services.video_workflow import (
    VideoWorkflowService,
    WorkflowConflict,
    WorkflowNotFound,
    WorkflowValidation,
    build_default_video_workflow,
)
from app.backend.services.youtube_publisher import (
    PublishRejected,
    PublisherStatus,
)


KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=KST)


class FakeRenderer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []
        self.observed_status = None

    def render(self, storyboard, *, output_path, music_path):
        self.observed_status = store.VIDEO_JOBS[next(iter(store.VIDEO_JOBS))][
            "render_status"
        ]
        self.calls.append((storyboard, output_path, music_path))
        if self.fail:
            raise RuntimeError("renderer detail must stay private")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"verified-mp4")
        return RenderResult(
            output_path=output_path,
            sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            duration_sec=12.5,
            width=1080,
            height=1920,
            video_codec="h264",
            audio_codec="aac",
            music_warning="music_unavailable" if music_path is None else None,
        )


class FakePublisher:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.requests = []

    def status(self):
        return PublisherStatus(True, "demo_merchant_channel", True)

    def publish(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return "youtube_123"


class FakeTrack:
    key = "practical_01"

    def __init__(self, path: Path) -> None:
        self.path = path


class FakeCatalog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def select_for_tone(self, tone: str):
        assert tone == "practical"
        return FakeTrack(self.path)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.reset_for_tests()
    yield
    store.reset_for_tests()


@pytest.fixture
def board(tmp_path):
    image_path = tmp_path / "source.png"
    image_path.write_bytes(b"source-image")
    return Storyboard(
        result_id="res_1",
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


@pytest.fixture
def workflow(tmp_path, board):
    renderer = FakeRenderer()
    publisher = FakePublisher()
    service = VideoWorkflowService(
        renderer=renderer,
        music_catalog=None,
        publisher=publisher,
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        storyboard_builder=lambda _: board,
        fingerprint_builder=lambda _: board.source_fingerprint,
    )
    service.renderer = renderer
    service.publisher = publisher
    return service


def _rendered_job(workflow):
    job = workflow.create("res_1")
    workflow.run_render(job.video_job_id)
    return workflow.get(job.video_job_id)


def _next_commute_am() -> datetime:
    return datetime(2026, 8, 10, 8, 0, tzinfo=KST)


def test_create_persists_queued_job_and_rejects_active_duplicate(workflow):
    job = workflow.create("res_1")

    assert job.render_status is RenderStatus.QUEUED
    assert store.STORE_PATH.is_file()
    with pytest.raises(WorkflowConflict, match="이미"):
        workflow.create("res_1")


def test_create_attaches_job_id_to_history_for_ui_restart_recovery(workflow):
    store.HISTORY.append(
        {
            "product_id": "prd_1",
            "results": [{"result_id": "res_1"}],
        }
    )

    job = workflow.create("res_1")

    assert store.HISTORY[0]["results"][0]["video_job_id"] == job.video_job_id


def test_create_maps_invalid_storyboard_to_validation_error(tmp_path):
    service = VideoWorkflowService(
        renderer=FakeRenderer(),
        music_catalog=None,
        publisher=FakePublisher(),
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        storyboard_builder=lambda _: (_ for _ in ()).throw(ValueError("not rush")),
        fingerprint_builder=lambda _: "unused",
    )

    with pytest.raises(WorkflowValidation, match="not rush"):
        service.create("res_afternoon")


def test_create_maps_unknown_result_to_not_found(tmp_path):
    service = VideoWorkflowService(
        renderer=FakeRenderer(),
        music_catalog=None,
        publisher=FakePublisher(),
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        storyboard_builder=lambda _: (_ for _ in ()).throw(
            StoryboardNotFound("missing")
        ),
        fingerprint_builder=lambda _: "unused",
    )

    with pytest.raises(WorkflowNotFound, match="missing"):
        service.create("res_missing")


def test_get_unknown_job_raises_not_found(workflow):
    with pytest.raises(WorkflowNotFound):
        workflow.get("missing")


def test_run_render_persists_processing_before_renderer_and_warning(workflow):
    job = workflow.create("res_1")

    workflow.run_render(job.video_job_id)

    rendered = workflow.get(job.video_job_id)
    assert workflow.renderer.observed_status == "processing"
    assert rendered.render_status is RenderStatus.COMPLETED
    assert rendered.video_sha256 == hashlib.sha256(b"verified-mp4").hexdigest()
    assert rendered.music_warning == "music_unavailable"
    assert rendered.video_url == f"/files/videos/{job.video_job_id}.mp4"


def test_run_render_records_sanitized_failure(tmp_path, board):
    service = VideoWorkflowService(
        renderer=FakeRenderer(fail=True),
        music_catalog=None,
        publisher=FakePublisher(),
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        storyboard_builder=lambda _: board,
        fingerprint_builder=lambda _: board.source_fingerprint,
    )
    job = service.create("res_1")

    service.run_render(job.video_job_id)

    failed = service.get(job.video_job_id)
    assert failed.render_status is RenderStatus.FAILED
    assert "renderer detail" not in (failed.error_message or "")


def test_renderer_uses_verified_music_when_catalog_exists(tmp_path, board):
    music_path = tmp_path / "music.mp3"
    music_path.write_bytes(b"licensed")
    renderer = FakeRenderer()
    service = VideoWorkflowService(
        renderer=renderer,
        music_catalog=FakeCatalog(music_path),
        publisher=FakePublisher(),
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        storyboard_builder=lambda _: board,
        fingerprint_builder=lambda _: board.source_fingerprint,
    )
    job = service.create("res_1")

    service.run_render(job.video_job_id)

    assert renderer.calls[0][2] == music_path
    assert service.get(job.video_job_id).music_key == "practical_01"


def test_approval_requires_completed_render(workflow):
    job = workflow.create("res_1")
    with pytest.raises(WorkflowConflict, match="렌더링 완료"):
        workflow.approve(
            job.video_job_id,
            activation_at=_next_commute_am(),
            publish_to_youtube=False,
            allow_silent=False,
        )


def test_silent_preview_requires_explicit_confirmation(workflow):
    job = _rendered_job(workflow)

    with pytest.raises(WorkflowConflict, match="무음"):
        workflow.approve(
            job.video_job_id,
            activation_at=_next_commute_am(),
            publish_to_youtube=False,
            allow_silent=False,
        )


@pytest.mark.parametrize(
    "activation_at",
    [
        datetime(2026, 8, 8, 12, 5, tzinfo=KST),
        datetime(2026, 8, 10, 9, 30, tzinfo=KST),
        datetime(2026, 8, 10, 8, 0),
    ],
)
def test_approval_validates_lead_window_and_timezone(workflow, activation_at):
    job = _rendered_job(workflow)

    with pytest.raises(WorkflowValidation):
        workflow.approve(
            job.video_job_id,
            activation_at=activation_at,
            publish_to_youtube=False,
            allow_silent=True,
        )


def test_approval_rejects_changed_source_or_video(workflow, board):
    job = _rendered_job(workflow)
    workflow._fingerprint_builder = lambda _: "changed"
    with pytest.raises(WorkflowConflict, match="원본"):
        workflow.approve(
            job.video_job_id,
            activation_at=_next_commute_am(),
            publish_to_youtube=False,
            allow_silent=True,
        )

    workflow._fingerprint_builder = lambda _: board.source_fingerprint
    (workflow._video_dir / f"{job.video_job_id}.mp4").write_bytes(b"changed")
    with pytest.raises(WorkflowConflict, match="영상"):
        workflow.approve(
            job.video_job_id,
            activation_at=_next_commute_am(),
            publish_to_youtube=False,
            allow_silent=True,
        )


def test_identical_approval_is_idempotent_but_changes_are_rejected(workflow):
    job = _rendered_job(workflow)
    approved = workflow.approve(
        job.video_job_id,
        activation_at=_next_commute_am(),
        publish_to_youtube=True,
        allow_silent=True,
    )

    repeated = workflow.approve(
        job.video_job_id,
        activation_at=_next_commute_am(),
        publish_to_youtube=True,
        allow_silent=True,
    )
    assert repeated == approved
    with pytest.raises(WorkflowConflict, match="변경"):
        workflow.approve(
            job.video_job_id,
            activation_at=_next_commute_am() + timedelta(days=1),
            publish_to_youtube=True,
            allow_silent=True,
        )


def test_youtube_failure_keeps_internal_approval(tmp_path, board):
    publisher = FakePublisher(error=PublishRejected("external detail"))
    service = VideoWorkflowService(
        renderer=FakeRenderer(),
        music_catalog=None,
        publisher=publisher,
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        storyboard_builder=lambda _: board,
        fingerprint_builder=lambda _: board.source_fingerprint,
    )
    job = _rendered_job(service)
    service.approve(
        job.video_job_id,
        activation_at=_next_commute_am(),
        publish_to_youtube=True,
        allow_silent=True,
    )

    service.run_publish(job.video_job_id)

    stored = service.get(job.video_job_id)
    assert stored.approval_status is ApprovalStatus.APPROVED
    assert stored.publish_status is PublishStatus.FAILED
    assert "external detail" not in (stored.youtube_error or "")


def test_successful_publish_and_safe_status(workflow):
    job = _rendered_job(workflow)
    workflow.approve(
        job.video_job_id,
        activation_at=_next_commute_am(),
        publish_to_youtube=True,
        allow_silent=True,
    )

    workflow.run_publish(job.video_job_id)

    published = workflow.get(job.video_job_id)
    assert published.publish_status is PublishStatus.SCHEDULED
    assert published.youtube_video_id == "youtube_123"
    assert workflow.youtube_status() == {
        "configured": True,
        "connection_id": "demo_merchant_channel",
        "token_available": True,
    }


def test_reject_only_works_while_approval_is_pending(workflow):
    job = workflow.create("res_1")

    rejected = workflow.reject(job.video_job_id)

    assert rejected.approval_status is ApprovalStatus.REJECTED
    with pytest.raises(WorkflowConflict):
        workflow.reject(job.video_job_id)


def test_default_workflow_is_safe_without_external_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YOUTUBE_UPLOAD_ENABLED", "false")
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(tmp_path / "missing-token.json"))
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRETS_FILE", str(tmp_path / "missing-client.json"))

    service = build_default_video_workflow()

    assert service.youtube_status() == {
        "configured": False,
        "connection_id": "demo_merchant_channel",
        "token_available": False,
    }
