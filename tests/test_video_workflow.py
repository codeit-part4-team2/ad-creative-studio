import hashlib
import threading
import wave
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from PIL import Image

from app.backend.schemas.video import ApprovalStatus, PublishStatus, RenderStatus
from app.backend.services import store
from app.backend.services.comic_script import ComicLineKind
from app.backend.services.scene_images import SceneImage, SceneImageSet
from app.backend.services.storyboard import Storyboard, StoryboardNotFound, StoryboardScene
from app.backend.services.tts_provider import TTSAudio
from app.backend.services.video_renderer import RenderResult
from app.backend.services.video_workflow import (
    VideoWorkflowService,
    WorkflowConflict,
    WorkflowNotFound,
    WorkflowValidation,
    build_default_video_workflow,
)
from app.backend.services.youtube_publisher import PublishRejected, PublisherStatus


KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=KST)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeSceneProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def build(self, *, storyboard, product_image_url, output_dir):
        self.calls.append(
            {
                "storyboard": storyboard,
                "product_image_url": product_image_url,
                "output_dir": output_dir,
            }
        )
        if self.fail:
            raise RuntimeError("private scene provider detail")
        images: list[SceneImage] = []
        for purpose, color in (("hero", "navy"), ("self_aware", "red"), ("benefit", "green")):
            path = output_dir / f"{purpose}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (32, 32), color).save(path)
            images.append(SceneImage(purpose, path.resolve(), _sha256(path), "fake"))
        return SceneImageSet(images=tuple(images))


class FakeTTSProvider:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def synthesize(self, spoken_text, output_path):
        self.texts.append(spoken_text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8_000)
            wav_file.writeframes(b"\x00\x00" * 800)
        return TTSAudio(
            path=output_path.resolve(),
            duration_sec=0.1,
            sha256=_sha256(output_path),
            engine="melotts-korean",
            voice_preset="deadpan-ai-v1",
        )


class FakeRenderer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, object]] = []
        self.observed_status: str | None = None

    def render(self, storyboard, *, scene_images, speech_audio, output_path):
        self.observed_status = store.VIDEO_JOBS[next(iter(store.VIDEO_JOBS))]["render_status"]
        self.calls.append(
            {
                "storyboard": storyboard,
                "scene_images": scene_images,
                "speech_audio": speech_audio,
                "output_path": output_path,
            }
        )
        if self.fail:
            raise RuntimeError("renderer detail must stay private")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"verified-mp4")
        audio_digest = hashlib.sha256(
            "".join(audio.sha256 for audio in speech_audio).encode("ascii")
        ).hexdigest()
        return RenderResult(
            output_path=output_path.resolve(),
            sha256=_sha256(output_path),
            duration_sec=12.5,
            width=1080,
            height=1920,
            video_codec="h264",
            audio_codec="aac",
            tts_audio_sha256=audio_digest,
            scene_image_sha256s=scene_images.sha256s,
            caption_layout_version="bright-outline-v1",
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
        return f"youtube_{len(self.requests)}"


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.reset_for_tests()
    yield
    store.reset_for_tests()


@pytest.fixture
def board(tmp_path):
    image_path = tmp_path / "source.png"
    Image.new("RGB", (32, 32), "navy").save(image_path)
    scenes = (
        StoryboardScene("휴대용 선풍기입니다.", 2.0, kind=ComicLineKind.INTRO, image_purpose="hero"),
        StoryboardScene(
            "저는 시간을 느끼지 못합니다.",
            2.0,
            kind=ComicLineKind.SELF_AWARE,
            image_purpose="self_aware",
        ),
        StoryboardScene("장점은 저소음입니다.", 2.0, kind=ComicLineKind.BENEFIT, image_purpose="benefit"),
        StoryboardScene("출근 전에 확인해 보세요.", 2.0, kind=ComicLineKind.CTA, image_purpose="cta"),
    )
    return Storyboard(
        result_id="res_1",
        product_id="prd_1",
        tone="practical",
        time_slot="commute_am",
        product_name="휴대용 선풍기",
        image_path=image_path,
        scenes=scenes,
        source_fingerprint="a" * 64,
        script_version="deadpan-ai-v1",
        pronunciation_review_required=False,
    )


def _board_for_result(board: Storyboard, result_id: str) -> Storyboard:
    return Storyboard(
        result_id=result_id,
        product_id=board.product_id,
        tone=board.tone,
        time_slot=board.time_slot,
        product_name=board.product_name,
        image_path=board.image_path,
        scenes=board.scenes,
        source_fingerprint=board.source_fingerprint,
        script_version=board.script_version,
        pronunciation_review_required=board.pronunciation_review_required,
    )


def _service(tmp_path, board, *, renderer=None, publisher=None, scene_provider=None):
    renderer = renderer or FakeRenderer()
    publisher = publisher or FakePublisher()
    scene_provider = scene_provider or FakeSceneProvider()
    tts_provider = FakeTTSProvider()
    service = VideoWorkflowService(
        renderer=renderer,
        scene_image_provider=scene_provider,
        tts_provider=tts_provider,
        publisher=publisher,
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        work_dir=tmp_path / "video-work",
        storyboard_builder=lambda result_id: _board_for_result(board, result_id),
        fingerprint_builder=lambda _result_id: board.source_fingerprint,
        product_image_url_builder=lambda _product_id: "/files/uploads/prd_1.png",
    )
    service.renderer = renderer
    service.publisher = publisher
    service.scene_provider = scene_provider
    service.tts_provider = tts_provider
    return service


@pytest.fixture
def workflow(tmp_path, board):
    return _service(tmp_path, board)


def _rendered_job(workflow, result_id="res_1"):
    job = workflow.create(result_id)
    workflow.run_render(job.video_job_id)
    return workflow.get(job.video_job_id)


def _next_commute_am() -> datetime:
    return datetime(2026, 8, 10, 8, 0, tzinfo=KST)


def test_create_persists_script_and_rejects_active_duplicate(workflow):
    job = workflow.create("res_1")

    assert job.render_status is RenderStatus.QUEUED
    assert job.script_version == "deadpan-ai-v1"
    assert len(job.script_lines) == 4
    assert store.STORE_PATH.is_file()
    with pytest.raises(WorkflowConflict, match="이미"):
        workflow.create("res_1")


def test_create_maps_invalid_and_unknown_storyboards(tmp_path):
    common = dict(
        renderer=FakeRenderer(),
        scene_image_provider=FakeSceneProvider(),
        tts_provider=FakeTTSProvider(),
        publisher=FakePublisher(),
        now=lambda: NOW,
        video_dir=tmp_path / "videos",
        work_dir=tmp_path / "work",
        fingerprint_builder=lambda _: "unused",
        product_image_url_builder=lambda _: "/files/uploads/p.png",
    )
    invalid = VideoWorkflowService(
        **common,
        storyboard_builder=lambda _: (_ for _ in ()).throw(ValueError("not rush")),
    )
    missing = VideoWorkflowService(
        **common,
        storyboard_builder=lambda _: (_ for _ in ()).throw(StoryboardNotFound("missing")),
    )

    with pytest.raises(WorkflowValidation, match="not rush"):
        invalid.create("res_bad")
    with pytest.raises(WorkflowNotFound, match="missing"):
        missing.create("res_missing")


def test_run_render_persists_tts_scene_and_caption_integrity(workflow):
    job = _rendered_job(workflow)

    assert workflow.renderer.observed_status == "processing"
    assert job.render_status is RenderStatus.COMPLETED
    assert job.video_sha256 == hashlib.sha256(b"verified-mp4").hexdigest()
    assert job.tts_engine == "melotts-korean"
    assert job.tts_voice_preset == "deadpan-ai-v1"
    assert len(job.tts_audio_sha256 or "") == 64
    assert len(job.scene_image_sha256s) == 3
    assert job.caption_layout_version == "bright-outline-v1"
    assert workflow.tts_provider.texts == [scene.spoken_text for scene in workflow.renderer.calls[0]["storyboard"].scenes]


def test_concurrent_render_requests_use_service_wide_queue(tmp_path, board):
    first_started = threading.Event()
    release_first = threading.Event()
    call_count = 0
    call_lock = threading.Lock()

    class BlockingRenderer(FakeRenderer):
        def render(self, storyboard, *, scene_images, speech_audio, output_path):
            nonlocal call_count
            with call_lock:
                call_count += 1
                current = call_count
            if current == 1:
                first_started.set()
                assert release_first.wait(timeout=3)
            return super().render(
                storyboard,
                scene_images=scene_images,
                speech_audio=speech_audio,
                output_path=output_path,
            )

    service = _service(tmp_path, board, renderer=BlockingRenderer())
    first = service.create("res_1")
    second = service.create("res_2")
    threads = [
        threading.Thread(target=service.run_render, args=(job.video_job_id,))
        for job in (first, second)
    ]
    threads[0].start()
    assert first_started.wait(timeout=1)
    threads[1].start()
    release_first.set()
    for thread in threads:
        thread.join(timeout=5)

    assert service.get(first.video_job_id).render_status is RenderStatus.COMPLETED
    assert service.get(second.video_job_id).render_status is RenderStatus.COMPLETED


def test_run_render_records_sanitized_failure(tmp_path, board):
    service = _service(tmp_path, board, renderer=FakeRenderer(fail=True))
    job = service.create("res_1")

    service.run_render(job.video_job_id)

    failed = service.get(job.video_job_id)
    assert failed.render_status is RenderStatus.FAILED
    assert "renderer detail" not in (failed.error_message or "")


def test_approval_requires_complete_integrity_and_pronunciation_review(workflow):
    queued = workflow.create("res_1")
    with pytest.raises(WorkflowConflict, match="렌더링 완료"):
        workflow.approve(queued.video_job_id, activation_at=_next_commute_am(), publish_to_youtube=False)

    workflow.run_render(queued.video_job_id)
    raw = store.VIDEO_JOBS[queued.video_job_id]
    raw["pronunciation_review_required"] = True
    with pytest.raises(WorkflowConflict, match="발음"):
        workflow.approve(queued.video_job_id, activation_at=_next_commute_am(), publish_to_youtube=False)

    raw["pronunciation_review_required"] = False
    raw["tts_audio_sha256"] = None
    with pytest.raises(WorkflowConflict, match="TTS"):
        workflow.approve(queued.video_job_id, activation_at=_next_commute_am(), publish_to_youtube=False)


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
        workflow.approve(job.video_job_id, activation_at=activation_at, publish_to_youtube=False)


def test_approval_rejects_changed_source_or_video(workflow, board):
    job = _rendered_job(workflow)
    workflow._fingerprint_builder = lambda _: "changed"
    with pytest.raises(WorkflowConflict, match="원본"):
        workflow.approve(job.video_job_id, activation_at=_next_commute_am(), publish_to_youtube=False)

    workflow._fingerprint_builder = lambda _: board.source_fingerprint
    (workflow._video_dir / f"{job.video_job_id}.mp4").write_bytes(b"changed")
    with pytest.raises(WorkflowConflict, match="영상"):
        workflow.approve(job.video_job_id, activation_at=_next_commute_am(), publish_to_youtube=False)


def test_identical_approval_is_idempotent_but_changes_are_rejected(workflow):
    job = _rendered_job(workflow)
    approved = workflow.approve(
        job.video_job_id,
        activation_at=_next_commute_am(),
        publish_to_youtube=True,
    )
    repeated = workflow.approve(
        job.video_job_id,
        activation_at=_next_commute_am(),
        publish_to_youtube=True,
    )
    assert repeated == approved
    with pytest.raises(WorkflowConflict, match="변경"):
        workflow.approve(
            job.video_job_id,
            activation_at=_next_commute_am() + timedelta(days=1),
            publish_to_youtube=True,
        )


def test_youtube_failure_keeps_internal_approval(tmp_path, board):
    service = _service(tmp_path, board, publisher=FakePublisher(error=PublishRejected("external detail")))
    job = _rendered_job(service)
    service.approve(job.video_job_id, activation_at=_next_commute_am(), publish_to_youtube=True)

    service.run_publish(job.video_job_id)

    stored = service.get(job.video_job_id)
    assert stored.approval_status is ApprovalStatus.APPROVED
    assert stored.publish_status is PublishStatus.FAILED
    assert "external detail" not in (stored.youtube_error or "")


def test_concurrent_publish_jobs_wait_and_never_stay_pending(tmp_path, board):
    first_started = threading.Event()
    release_first = threading.Event()

    class BlockingPublisher(FakePublisher):
        def publish(self, request):
            self.requests.append(request)
            if len(self.requests) == 1:
                first_started.set()
                assert release_first.wait(timeout=3)
            return f"youtube_{len(self.requests)}"

    publisher = BlockingPublisher()
    service = _service(tmp_path, board, publisher=publisher)
    jobs = [_rendered_job(service, result_id) for result_id in ("res_1", "res_2")]
    for job in jobs:
        service.approve(job.video_job_id, activation_at=_next_commute_am(), publish_to_youtube=True)
    errors: list[Exception] = []

    def publish(video_job_id: str) -> None:
        try:
            service.run_publish(video_job_id)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish, args=(job.video_job_id,)) for job in jobs]
    threads[0].start()
    assert first_started.wait(timeout=1)
    threads[1].start()
    release_first.set()
    for thread in threads:
        thread.join(timeout=5)

    assert errors == []
    assert all(service.get(job.video_job_id).publish_status is PublishStatus.SCHEDULED for job in jobs)


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
