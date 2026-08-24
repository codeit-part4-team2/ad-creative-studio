from __future__ import annotations

import hashlib
import logging
import os
import shutil
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

from app.backend.schemas.video import ApprovalStatus, PublishStatus, RenderStatus, VideoJob
from app.backend.services import store
from app.backend.services.scene_images import SceneImageProvider
from app.backend.services.storyboard import (
    Storyboard,
    StoryboardNotFound,
    build_storyboard,
    current_source_fingerprint,
    find_tone_result,
)
from app.backend.services.tts_provider import (
    MeloTTSProvider,
    TTSProvider,
    TTSRuntimeUnavailable,
)
from app.backend.services.video_renderer import (
    RushHourVideoRenderer,
    VideoRuntimeUnavailable,
)
from app.backend.services.youtube_publisher import (
    AuthenticationRequired,
    DisabledPublisher,
    GoogleYouTubePublisher,
    PublishRejected,
    PublishRequest,
    Publisher,
    PublishUncertain,
    ScheduleExpired,
)


KST = ZoneInfo("Asia/Seoul")
MINIMUM_LEAD_TIME = timedelta(minutes=10)
SLOT_WINDOWS = {
    "commute_am": (time(8, 0), time(9, 30)),
    "commute_pm": (time(18, 0), time(19, 30)),
}
DEFAULT_FAILED_WORK_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_COMPLETED_WORK_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_FAILED_WORK_CLEANUP_INTERVAL_SECONDS = 60 * 60
COMPLETED_INTERMEDIATE_FILES = {
    "images": (
        "scene_hero.png",
        "scene_self_aware.png",
        "scene_benefit.png",
    ),
    "audio": (
        "line-00.wav",
        "line-01.wav",
        "line-02.wav",
        "line-03.wav",
    ),
}
LOGGER = logging.getLogger("ad_creative_studio.video_workflow")


class WorkflowError(RuntimeError):
    pass


class WorkflowNotFound(WorkflowError):
    pass


class WorkflowConflict(WorkflowError):
    pass


class WorkflowValidation(WorkflowError):
    pass


@contextmanager
def _track_render_stage(
    *,
    stage: str,
    video_job_id: str,
    result_id: str,
) -> Iterator[None]:
    context = {
        "render_stage": stage,
        "video_job_id": video_job_id,
        "result_id": result_id,
    }
    started_at = perf_counter()
    LOGGER.info(
        "video render stage started stage=%s video_job_id=%s result_id=%s",
        stage,
        video_job_id,
        result_id,
        extra={**context, "render_event": "started"},
    )
    try:
        yield
    except Exception as exc:
        duration_ms = round((perf_counter() - started_at) * 1000)
        LOGGER.exception(
            (
                "video render failed stage=%s video_job_id=%s "
                "result_id=%s exception_type=%s duration_ms=%d"
            ),
            stage,
            video_job_id,
            result_id,
            type(exc).__name__,
            duration_ms,
            extra={
                **context,
                "render_event": "failed",
                "exception_type": type(exc).__name__,
                "duration_ms": duration_ms,
            },
        )
        raise
    else:
        duration_ms = round((perf_counter() - started_at) * 1000)
        LOGGER.info(
            (
                "video render stage completed stage=%s video_job_id=%s "
                "result_id=%s duration_ms=%d"
            ),
            stage,
            video_job_id,
            result_id,
            duration_ms,
            extra={
                **context,
                "render_event": "completed",
                "duration_ms": duration_ms,
            },
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stored_product_image_url(product_id: str) -> str:
    product = store.PRODUCTS.get(product_id)
    if not isinstance(product, dict):
        raise WorkflowValidation("영상용 원본 상품을 찾을 수 없습니다")
    image_url = product.get("image_url")
    if not isinstance(image_url, str) or not image_url.strip():
        raise WorkflowValidation("영상용 원본 상품 이미지가 없습니다")
    return image_url


class VideoWorkflowService:
    def __init__(
        self,
        *,
        renderer: RushHourVideoRenderer,
        scene_image_provider: SceneImageProvider,
        tts_provider: TTSProvider,
        publisher: Publisher,
        now: Callable[[], datetime],
        video_dir: Path = Path("data/videos"),
        work_dir: Path = Path("var/video-work"),
        storyboard_builder: Callable[[str], Storyboard] = build_storyboard,
        fingerprint_builder: Callable[[str], str] = current_source_fingerprint,
        product_image_url_builder: Callable[[str], str] = _stored_product_image_url,
        failed_work_ttl_seconds: int = DEFAULT_FAILED_WORK_TTL_SECONDS,
        completed_work_ttl_seconds: int = DEFAULT_COMPLETED_WORK_TTL_SECONDS,
        failed_work_cleanup_interval_seconds: int = (
            DEFAULT_FAILED_WORK_CLEANUP_INTERVAL_SECONDS
        ),
    ) -> None:
        if failed_work_ttl_seconds < 0:
            raise ValueError("failed work TTL must not be negative")
        if completed_work_ttl_seconds < 0:
            raise ValueError("completed work TTL must not be negative")
        if failed_work_cleanup_interval_seconds < 0:
            raise ValueError("failed work cleanup interval must not be negative")
        self._renderer = renderer
        self._scene_image_provider = scene_image_provider
        self._tts_provider = tts_provider
        self._publisher = publisher
        self._now = now
        self._video_dir = video_dir
        self._work_dir = work_dir
        self._storyboard_builder = storyboard_builder
        self._fingerprint_builder = fingerprint_builder
        self._product_image_url_builder = product_image_url_builder
        self._failed_work_ttl_seconds = failed_work_ttl_seconds
        self._completed_work_ttl_seconds = completed_work_ttl_seconds
        self._work_cleanup_interval_seconds = failed_work_cleanup_interval_seconds
        self._state_lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._publish_lock = threading.Lock()
        self._active_job_ids_by_result: dict[str, set[str]] = {}
        self._failed_job_updated_at: dict[str, datetime] = {}
        self._completed_job_updated_at: dict[str, datetime] = {}
        self._next_work_cleanup_at: datetime | None = None
        self._job_index_complete = True
        self._initialize_job_indexes()

    def _clock(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError("workflow clock must return an aware datetime")
        return value

    @staticmethod
    def _stored(job: VideoJob) -> dict:
        return job.model_dump(mode="json")

    @staticmethod
    def _is_active(job: VideoJob) -> bool:
        return (
            job.approval_status is not ApprovalStatus.REJECTED
            and job.render_status is not RenderStatus.FAILED
        )

    def _initialize_job_indexes(self) -> None:
        for raw_job in store.VIDEO_JOBS.values():
            try:
                job = VideoJob.model_validate(raw_job)
            except ValueError as exc:
                result_id = raw_job.get("result_id")
                video_job_id = raw_job.get("video_job_id")
                if (
                    isinstance(result_id, str)
                    and result_id
                    and isinstance(video_job_id, str)
                    and video_job_id
                ):
                    self._active_job_ids_by_result.setdefault(result_id, set()).add(
                        video_job_id
                    )
                    LOGGER.error(
                        "invalid persisted video job %s (%s); reserving result %s",
                        video_job_id,
                        type(exc).__name__,
                        result_id,
                    )
                else:
                    self._job_index_complete = False
                    LOGGER.error(
                        "persisted video job cannot be indexed (%s); blocking new jobs",
                        type(exc).__name__,
                    )
                continue
            self._update_job_indexes_locked(job)

    def _update_job_indexes_locked(self, job: VideoJob) -> None:
        if self._is_active(job):
            self._active_job_ids_by_result.setdefault(job.result_id, set()).add(
                job.video_job_id
            )
        else:
            active_job_ids = self._active_job_ids_by_result.get(job.result_id)
            if active_job_ids is not None:
                active_job_ids.discard(job.video_job_id)
                if not active_job_ids:
                    self._active_job_ids_by_result.pop(job.result_id, None)

        if (
            job.render_status is RenderStatus.FAILED
            and job.updated_at.tzinfo is not None
            and job.updated_at.utcoffset() is not None
        ):
            self._failed_job_updated_at[job.video_job_id] = job.updated_at
        else:
            self._failed_job_updated_at.pop(job.video_job_id, None)

        if (
            job.render_status is RenderStatus.COMPLETED
            and job.updated_at.tzinfo is not None
            and job.updated_at.utcoffset() is not None
        ):
            self._completed_job_updated_at[job.video_job_id] = job.updated_at
        else:
            self._completed_job_updated_at.pop(job.video_job_id, None)

    def _persist_locked(self, job: VideoJob) -> VideoJob:
        store.VIDEO_JOBS[job.video_job_id] = self._stored(job)
        store.save()
        self._update_job_indexes_locked(job)
        return job

    def _get_locked(self, video_job_id: str) -> VideoJob:
        raw_job = store.VIDEO_JOBS.get(video_job_id)
        if raw_job is None:
            raise WorkflowNotFound("영상 작업을 찾을 수 없습니다")
        return VideoJob.model_validate(raw_job)

    def get(self, video_job_id: str) -> VideoJob:
        with self._state_lock:
            return self._get_locked(video_job_id)

    def create(self, result_id: str) -> VideoJob:
        try:
            storyboard = self._storyboard_builder(result_id)
        except StoryboardNotFound as exc:
            raise WorkflowNotFound(str(exc)) from exc
        except ValueError as exc:
            raise WorkflowValidation(str(exc)) from exc

        now = self._clock()
        self._cleanup_stale_work_dirs(now=now)
        with self._state_lock:
            if not self._job_index_complete:
                raise WorkflowConflict("저장된 영상 작업을 먼저 복구해야 합니다")
            if result_id in self._active_job_ids_by_result:
                raise WorkflowConflict("이 결과에는 이미 활성 영상 작업이 있습니다")
            job = VideoJob(
                video_job_id=f"video_{uuid.uuid4().hex[:12]}",
                result_id=result_id,
                product_id=storyboard.product_id,
                tone=storyboard.tone,
                time_slot=storyboard.time_slot,
                source_fingerprint=storyboard.source_fingerprint,
                script_version=storyboard.script_version,
                script_lines=tuple(scene.display_text for scene in storyboard.scenes),
                pronunciation_review_required=storyboard.pronunciation_review_required,
                created_at=now,
                updated_at=now,
            )
            _, tone_result = find_tone_result(result_id)
            if tone_result is not None:
                tone_result["video_job_id"] = job.video_job_id
            return self._persist_locked(job)

    def _cleanup_stale_work_dirs(self, *, now: datetime) -> None:
        if (
            self._failed_work_ttl_seconds == 0
            and self._completed_work_ttl_seconds == 0
        ):
            return
        with self._state_lock:
            if (
                self._next_work_cleanup_at is not None
                and now < self._next_work_cleanup_at
            ):
                return
            self._next_work_cleanup_at = now + timedelta(
                seconds=self._work_cleanup_interval_seconds
            )
            expired_jobs: list[tuple[str, RenderStatus, datetime]] = []
            if self._failed_work_ttl_seconds > 0:
                failed_cutoff = now - timedelta(
                    seconds=self._failed_work_ttl_seconds
                )
                expired_jobs.extend(
                    (video_job_id, RenderStatus.FAILED, updated_at)
                    for video_job_id, updated_at in self._failed_job_updated_at.items()
                    if updated_at < failed_cutoff
                )
            if self._completed_work_ttl_seconds > 0:
                completed_cutoff = now - timedelta(
                    seconds=self._completed_work_ttl_seconds
                )
                expired_jobs.extend(
                    (video_job_id, RenderStatus.COMPLETED, updated_at)
                    for video_job_id, updated_at in self._completed_job_updated_at.items()
                    if updated_at < completed_cutoff
                )

        for video_job_id, render_status, expected_updated_at in expired_jobs:
            try:
                candidate = self._safe_job_work_path(video_job_id)
            except WorkflowValidation:
                continue
            if render_status is RenderStatus.COMPLETED:
                try:
                    with self._state_lock:
                        if (
                            self._completed_job_updated_at.get(video_job_id)
                            != expected_updated_at
                        ):
                            continue
                        if candidate.is_dir():
                            self._remove_completed_intermediates(candidate)
                        self._remove_terminal_work_index_locked(
                            video_job_id,
                            render_status,
                        )
                except OSError:
                    LOGGER.warning(
                        "failed to remove expired %s video work directory for %s",
                        render_status.value,
                        video_job_id,
                        exc_info=True,
                    )
                continue
            if not candidate.is_dir():
                with self._state_lock:
                    self._remove_terminal_work_index_locked(
                        video_job_id,
                        render_status,
                    )
                continue
            try:
                shutil.rmtree(candidate)
            except OSError:
                LOGGER.warning(
                    "failed to remove expired %s video work directory for %s",
                    render_status.value,
                    video_job_id,
                    exc_info=True,
                )
            else:
                with self._state_lock:
                    self._remove_terminal_work_index_locked(
                        video_job_id,
                        render_status,
                    )

    @staticmethod
    def _remove_completed_intermediates(job_dir: Path) -> None:
        resolved_job_dir = job_dir.resolve()
        for directory_name, managed_filenames in COMPLETED_INTERMEDIATE_FILES.items():
            intermediate_dir = job_dir / directory_name
            if intermediate_dir.is_symlink():
                raise OSError(
                    f"refusing to remove symlinked intermediate {directory_name}"
                )
            if not intermediate_dir.is_dir():
                continue

            resolved_intermediate_dir = intermediate_dir.resolve()
            if not resolved_intermediate_dir.is_relative_to(resolved_job_dir):
                raise OSError(
                    f"refusing to remove escaped intermediate {directory_name}"
                )

            for filename in managed_filenames:
                candidate = intermediate_dir / filename
                if candidate.is_symlink():
                    raise OSError(
                        f"refusing to remove symlinked intermediate file {filename}"
                    )
                if not candidate.exists():
                    continue
                resolved_candidate = candidate.resolve()
                if not resolved_candidate.is_relative_to(resolved_intermediate_dir):
                    raise OSError(
                        f"refusing to remove escaped intermediate file {filename}"
                    )
                if not candidate.is_file():
                    raise OSError(
                        f"refusing to remove non-file intermediate {filename}"
                    )
                candidate.unlink()

            if next(intermediate_dir.iterdir(), None) is None:
                intermediate_dir.rmdir()

    def _remove_terminal_work_index_locked(
        self,
        video_job_id: str,
        render_status: RenderStatus,
    ) -> None:
        if render_status is RenderStatus.FAILED:
            self._failed_job_updated_at.pop(video_job_id, None)
        elif render_status is RenderStatus.COMPLETED:
            self._completed_job_updated_at.pop(video_job_id, None)

    def _safe_job_work_path(self, video_job_id: str) -> Path:
        root = self._work_dir.expanduser().resolve()
        candidate = root / video_job_id
        if candidate.is_symlink():
            raise WorkflowValidation("영상 작업 디렉터리가 올바르지 않습니다")
        resolved_candidate = candidate.resolve()
        if resolved_candidate == root or not resolved_candidate.is_relative_to(root):
            raise WorkflowValidation("영상 작업 디렉터리가 올바르지 않습니다")
        return resolved_candidate

    def _job_work_dir(self, video_job_id: str) -> Path:
        job_dir = self._safe_job_work_path(video_job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def run_render(self, video_job_id: str) -> None:
        with self._render_lock:
            with self._state_lock:
                job = self._get_locked(video_job_id)
                if job.render_status in {RenderStatus.COMPLETED, RenderStatus.FAILED}:
                    return
                if job.render_status is RenderStatus.PROCESSING:
                    raise WorkflowConflict("영상 렌더링이 이미 진행 중입니다")
                if job.render_status is not RenderStatus.QUEUED:
                    raise WorkflowConflict("대기 중인 영상만 렌더링할 수 있습니다")
                processing = job.model_copy(
                    update={
                        "render_status": RenderStatus.PROCESSING,
                        "error_message": None,
                        "updated_at": self._clock(),
                    }
                )
                self._persist_locked(processing)

            try:
                with _track_render_stage(
                    stage="storyboard",
                    video_job_id=video_job_id,
                    result_id=processing.result_id,
                ):
                    storyboard = self._storyboard_builder(processing.result_id)
                    if storyboard.source_fingerprint != processing.source_fingerprint:
                        raise WorkflowConflict("원본 광고가 변경되어 다시 생성해야 합니다")

                with _track_render_stage(
                    stage="runtime_validation",
                    video_job_id=video_job_id,
                    result_id=processing.result_id,
                ):
                    self._renderer.validate_runtime()
                    self._tts_provider.validate_runtime()

                with _track_render_stage(
                    stage="scene_images",
                    video_job_id=video_job_id,
                    result_id=processing.result_id,
                ):
                    job_dir = self._job_work_dir(video_job_id)
                    product_image_url = self._product_image_url_builder(
                        processing.product_id
                    )
                    scene_images = self._scene_image_provider.build(
                        storyboard=storyboard,
                        product_image_url=product_image_url,
                        output_dir=job_dir / "images",
                    )

                with _track_render_stage(
                    stage="tts",
                    video_job_id=video_job_id,
                    result_id=processing.result_id,
                ):
                    speech_audio = tuple(
                        self._tts_provider.synthesize(
                            scene.spoken_text,
                            job_dir / "audio" / f"line-{index:02d}.wav",
                        )
                        for index, scene in enumerate(storyboard.scenes)
                    )
                    if len({audio.engine for audio in speech_audio}) != 1:
                        raise WorkflowConflict("TTS 엔진이 장면별로 일치하지 않습니다")
                    if len({audio.voice_preset for audio in speech_audio}) != 1:
                        raise WorkflowConflict(
                            "TTS 음성 프리셋이 장면별로 일치하지 않습니다"
                        )

                with _track_render_stage(
                    stage="ffmpeg_render",
                    video_job_id=video_job_id,
                    result_id=processing.result_id,
                ):
                    rendered = self._renderer.render(
                        storyboard,
                        scene_images=scene_images,
                        speech_audio=speech_audio,
                        output_path=self._video_dir / f"{video_job_id}.mp4",
                    )
            except Exception as exc:
                if isinstance(exc, TTSRuntimeUnavailable):
                    error_message = "TTS 실행 환경이 준비되지 않았습니다"
                elif isinstance(exc, VideoRuntimeUnavailable):
                    error_message = "영상 렌더링 실행 환경이 준비되지 않았습니다"
                elif isinstance(exc, WorkflowConflict):
                    error_message = str(exc)
                else:
                    error_message = "영상 렌더링에 실패했습니다"
                with self._state_lock:
                    failed = self._get_locked(video_job_id).model_copy(
                        update={
                            "render_status": RenderStatus.FAILED,
                            "error_message": error_message,
                            "updated_at": self._clock(),
                        }
                    )
                    self._persist_locked(failed)
                return

            with self._state_lock:
                current = self._get_locked(video_job_id)
                if current.render_status is not RenderStatus.PROCESSING:
                    raise WorkflowConflict("영상 작업 상태가 렌더링 중 변경되었습니다")
                completed = current.model_copy(
                    update={
                        "render_status": RenderStatus.COMPLETED,
                        "video_url": f"/files/videos/{rendered.output_path.name}",
                        "video_sha256": rendered.sha256,
                        "script_version": storyboard.script_version,
                        "script_lines": tuple(scene.display_text for scene in storyboard.scenes),
                        "tts_engine": speech_audio[0].engine,
                        "tts_voice_preset": speech_audio[0].voice_preset,
                        "tts_audio_sha256": rendered.tts_audio_sha256,
                        "pronunciation_review_required": storyboard.pronunciation_review_required,
                        "scene_image_sha256s": rendered.scene_image_sha256s,
                        "caption_layout_version": rendered.caption_layout_version,
                        "error_message": None,
                        "updated_at": self._clock(),
                    }
                )
                _, tone_result = find_tone_result(completed.result_id)
                if tone_result is not None:
                    tone_result["video_url"] = completed.video_url
                self._persist_locked(completed)

    def _video_path(self, job: VideoJob) -> Path:
        if not job.video_url or not job.video_url.startswith("/files/videos/"):
            raise WorkflowConflict("완성 영상 경로가 올바르지 않습니다")
        video_root = self._video_dir.resolve()
        video_path = (video_root / Path(job.video_url).name).resolve()
        if not video_path.is_relative_to(video_root) or not video_path.is_file():
            raise WorkflowConflict("완성 영상 파일을 찾을 수 없습니다")
        return video_path

    def _validate_schedule(self, job: VideoJob, activation_at: datetime) -> None:
        if activation_at.tzinfo is None or activation_at.utcoffset() is None:
            raise WorkflowValidation("노출 시각에는 시간대 정보가 필요합니다")
        if activation_at < self._clock() + MINIMUM_LEAD_TIME:
            raise WorkflowValidation("노출 시각은 최소 10분 이후여야 합니다")
        local_time = activation_at.astimezone(KST).time().replace(tzinfo=None)
        window_start, window_end = SLOT_WINDOWS[job.time_slot]
        if not window_start <= local_time < window_end:
            raise WorkflowValidation("노출 시각이 선택한 러시아워 구간과 맞지 않습니다")

    def _validate_integrity(self, job: VideoJob) -> Path:
        try:
            source_fingerprint = self._fingerprint_builder(job.result_id)
        except ValueError as exc:
            raise WorkflowConflict("원본 광고를 다시 확인할 수 없습니다") from exc
        if source_fingerprint != job.source_fingerprint:
            raise WorkflowConflict("원본 광고가 변경되어 다시 생성해야 합니다")
        video_path = self._video_path(job)
        if not job.video_sha256 or _sha256(video_path) != job.video_sha256:
            raise WorkflowConflict("완성 영상이 변경되어 다시 생성해야 합니다")
        return video_path

    @staticmethod
    def _validate_render_metadata(
        job: VideoJob,
        *,
        pronunciation_confirmed: bool,
    ) -> None:
        if (
            job.pronunciation_review_required
            and job.pronunciation_reviewed_at is None
            and not pronunciation_confirmed
        ):
            raise WorkflowConflict("상품명 발음 검토가 끝나지 않았습니다")
        if not job.tts_audio_sha256 or len(job.tts_audio_sha256) != 64:
            raise WorkflowConflict("TTS 음성 무결성을 확인할 수 없습니다")
        if len(job.scene_image_sha256s) != 3 or len(set(job.scene_image_sha256s)) != 3:
            raise WorkflowConflict("서로 다른 장면 이미지 3장을 확인할 수 없습니다")
        if not job.caption_layout_version:
            raise WorkflowConflict("자막 레이아웃을 확인할 수 없습니다")

    def approve(
        self,
        video_job_id: str,
        *,
        activation_at: datetime,
        publish_to_youtube: bool,
        pronunciation_confirmed: bool = False,
    ) -> VideoJob:
        with self._state_lock:
            snapshot = self._get_locked(video_job_id)
        if snapshot.render_status is not RenderStatus.COMPLETED:
            raise WorkflowConflict("렌더링 완료 후 승인할 수 있습니다")
        if snapshot.approval_status is ApprovalStatus.REJECTED:
            raise WorkflowConflict("거절된 영상은 승인할 수 없습니다")
        self._validate_schedule(snapshot, activation_at)
        self._validate_render_metadata(
            snapshot,
            pronunciation_confirmed=pronunciation_confirmed,
        )
        self._validate_integrity(snapshot)

        requested_publish = snapshot.publish_status is not PublishStatus.NOT_REQUESTED
        if snapshot.approval_status is ApprovalStatus.APPROVED:
            if snapshot.activation_at == activation_at and requested_publish == publish_to_youtube:
                return snapshot
            raise WorkflowConflict("승인 후 예약 조건은 변경할 수 없습니다")

        with self._state_lock:
            current = self._get_locked(video_job_id)
            if current.updated_at != snapshot.updated_at:
                raise WorkflowConflict("검토 중 영상 작업 상태가 변경되었습니다")
            approved = current.model_copy(
                update={
                    "approval_status": ApprovalStatus.APPROVED,
                    "publish_status": PublishStatus.PENDING if publish_to_youtube else PublishStatus.NOT_REQUESTED,
                    "activation_at": activation_at,
                    "approved_at": self._clock(),
                    "pronunciation_reviewed_at": (
                        current.pronunciation_reviewed_at
                        or (
                            self._clock()
                            if current.pronunciation_review_required
                            and pronunciation_confirmed
                            else None
                        )
                    ),
                    "youtube_error": None,
                    "updated_at": self._clock(),
                }
            )
            return self._persist_locked(approved)

    def _publish_request(self, job: VideoJob, video_path: Path) -> PublishRequest:
        storyboard = self._storyboard_builder(job.result_id)
        headline = storyboard.scenes[0].display_text if storyboard.scenes else storyboard.product_name
        title = f"{storyboard.product_name} | {headline}"[:100]
        facts = [scene.display_text for scene in storyboard.scenes]
        return PublishRequest(
            video_path=video_path,
            title=title,
            description="\n\n".join(facts + ["#Shorts"]),
            tags=("Shorts", "제품광고", storyboard.tone),
            publish_at=job.activation_at,
        )

    def run_publish(self, video_job_id: str) -> None:
        with self._publish_lock:
            with self._state_lock:
                snapshot = self._get_locked(video_job_id)
            if snapshot.approval_status is not ApprovalStatus.APPROVED:
                raise WorkflowConflict("승인된 영상만 게시할 수 있습니다")
            if snapshot.publish_status in {
                PublishStatus.SCHEDULED,
                PublishStatus.FAILED,
                PublishStatus.AUTH_REQUIRED,
                PublishStatus.NEEDS_REVIEW,
                PublishStatus.SCHEDULE_EXPIRED,
            }:
                return
            if snapshot.publish_status is not PublishStatus.PENDING:
                raise WorkflowConflict("게시 대기 중인 영상만 업로드할 수 있습니다")
            if snapshot.activation_at is None:
                raise WorkflowConflict("게시 예약 시각이 없습니다")
            try:
                video_path = self._validate_integrity(snapshot)
                request = self._publish_request(snapshot, video_path)
                video_id = self._publisher.publish(request)
            except AuthenticationRequired:
                status, error, video_id = PublishStatus.AUTH_REQUIRED, "YouTube 인증이 필요합니다", None
            except ScheduleExpired:
                status, error, video_id = PublishStatus.SCHEDULE_EXPIRED, "YouTube 예약 시각이 지났습니다", None
            except PublishUncertain:
                status, error, video_id = PublishStatus.NEEDS_REVIEW, "YouTube 게시 결과를 수동으로 확인해야 합니다", None
            except WorkflowConflict:
                status, error, video_id = PublishStatus.NEEDS_REVIEW, "게시 전 영상 무결성을 다시 확인해야 합니다", None
            except PublishRejected:
                status, error, video_id = PublishStatus.FAILED, "YouTube 게시에 실패했습니다", None
            except Exception:
                status, error, video_id = PublishStatus.FAILED, "YouTube 게시에 실패했습니다", None
            else:
                status, error = PublishStatus.SCHEDULED, None
            with self._state_lock:
                current = self._get_locked(video_job_id)
                if current.updated_at != snapshot.updated_at:
                    raise WorkflowConflict("게시 중 영상 작업 상태가 변경되었습니다")
                self._persist_locked(
                    current.model_copy(
                        update={
                            "publish_status": status,
                            "youtube_video_id": video_id,
                            "youtube_error": error,
                            "updated_at": self._clock(),
                        }
                    )
                )

    def reject(self, video_job_id: str) -> VideoJob:
        with self._state_lock:
            job = self._get_locked(video_job_id)
            if job.approval_status is not ApprovalStatus.PENDING:
                raise WorkflowConflict("검토 대기 중인 영상만 거절할 수 있습니다")
            return self._persist_locked(
                job.model_copy(
                    update={
                        "approval_status": ApprovalStatus.REJECTED,
                        "updated_at": self._clock(),
                    }
                )
            )

    def youtube_status(self) -> dict[str, str | bool]:
        status = self._publisher.status()
        return {
            "configured": status.configured,
            "connection_id": status.connection_id,
            "token_available": status.token_available,
        }


def _external_file(path_value: str, *, repo_root: Path) -> Path | None:
    if not path_value.strip():
        return None
    path = Path(path_value).expanduser().resolve()
    if path.is_relative_to(repo_root.resolve()) or not path.is_file():
        return None
    return path


def _youtube_service_factory(token_path: Path) -> Callable[[], object]:
    def create_service() -> object:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials.from_authorized_user_file(
            str(token_path),
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    return create_service


def _nonnegative_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value.strip())
    except ValueError:
        value = -1
    if value < 0:
        LOGGER.warning(
            "invalid %s value %r; using default %d",
            name,
            raw_value,
            default,
        )
        return default
    return value


def build_default_video_workflow() -> VideoWorkflowService:
    repo_root = Path(__file__).resolve().parents[3]
    connection_id = os.getenv("YOUTUBE_CONNECTION_ID", "demo_merchant_channel")
    upload_enabled = os.getenv("YOUTUBE_UPLOAD_ENABLED", "false").strip().lower() == "true"
    token_path = _external_file(os.getenv("YOUTUBE_TOKEN_FILE", ""), repo_root=repo_root)
    client_path = _external_file(os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", ""), repo_root=repo_root)
    if upload_enabled and token_path is not None and client_path is not None:
        publisher: Publisher = GoogleYouTubePublisher(
            service_factory=_youtube_service_factory(token_path),
            connection_id=connection_id,
            token_available=True,
        )
    else:
        publisher = DisabledPublisher(connection_id)

    work_dir = Path(os.getenv("VIDEO_WORK_DIR", "var/video-work"))
    renderer = RushHourVideoRenderer(
        font_path=Path(os.getenv("VIDEO_FONT_PATH", "assets/fonts/NanumGothic-Regular.ttf")),
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
        preset=os.getenv("VIDEO_FFMPEG_PRESET", "veryfast"),
    )
    return VideoWorkflowService(
        renderer=renderer,
        scene_image_provider=SceneImageProvider(),
        tts_provider=MeloTTSProvider(output_root=work_dir),
        publisher=publisher,
        now=lambda: datetime.now(timezone.utc),
        video_dir=Path(os.getenv("VIDEO_DIR", "data/videos")),
        work_dir=work_dir,
        failed_work_ttl_seconds=_nonnegative_int_env(
            "VIDEO_FAILED_WORK_TTL_SECONDS",
            DEFAULT_FAILED_WORK_TTL_SECONDS,
        ),
        completed_work_ttl_seconds=_nonnegative_int_env(
            "VIDEO_COMPLETED_WORK_TTL_SECONDS",
            DEFAULT_COMPLETED_WORK_TTL_SECONDS,
        ),
        failed_work_cleanup_interval_seconds=_nonnegative_int_env(
            "VIDEO_FAILED_WORK_CLEANUP_INTERVAL_SECONDS",
            DEFAULT_FAILED_WORK_CLEANUP_INTERVAL_SECONDS,
        ),
    )
