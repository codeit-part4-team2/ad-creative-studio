from __future__ import annotations

import hashlib
import os
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.backend.schemas.video import (
    ApprovalStatus,
    PublishStatus,
    RenderStatus,
    VideoJob,
)
from app.backend.services import store
from app.backend.services.music_catalog import MusicCatalog
from app.backend.services.storyboard import (
    Storyboard,
    StoryboardNotFound,
    build_storyboard,
    current_source_fingerprint,
    find_tone_result,
)
from app.backend.services.video_renderer import RushHourVideoRenderer
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


class WorkflowError(RuntimeError):
    pass


class WorkflowNotFound(WorkflowError):
    pass


class WorkflowConflict(WorkflowError):
    pass


class WorkflowValidation(WorkflowError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class VideoWorkflowService:
    def __init__(
        self,
        *,
        renderer: RushHourVideoRenderer,
        music_catalog: MusicCatalog | None,
        publisher: Publisher,
        now: Callable[[], datetime],
        video_dir: Path = Path("data/videos"),
        storyboard_builder: Callable[[str], Storyboard] = build_storyboard,
        fingerprint_builder: Callable[[str], str] = current_source_fingerprint,
    ) -> None:
        self._renderer = renderer
        self._music_catalog = music_catalog
        self._publisher = publisher
        self._now = now
        self._video_dir = video_dir
        self._storyboard_builder = storyboard_builder
        self._fingerprint_builder = fingerprint_builder
        self._state_lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._publish_lock = threading.Lock()

    def _clock(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError("workflow clock must return an aware datetime")
        return value

    @staticmethod
    def _stored(job: VideoJob) -> dict:
        return job.model_dump(mode="json")

    def _persist_locked(self, job: VideoJob) -> VideoJob:
        store.VIDEO_JOBS[job.video_job_id] = self._stored(job)
        store.save()
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
        with self._state_lock:
            for raw_job in store.VIDEO_JOBS.values():
                candidate = VideoJob.model_validate(raw_job)
                if (
                    candidate.result_id == result_id
                    and candidate.approval_status is not ApprovalStatus.REJECTED
                    and candidate.render_status is not RenderStatus.FAILED
                ):
                    raise WorkflowConflict("이 결과에는 이미 활성 영상 작업이 있습니다")

            job = VideoJob(
                video_job_id=f"video_{uuid.uuid4().hex[:12]}",
                result_id=result_id,
                product_id=storyboard.product_id,
                tone=storyboard.tone,
                time_slot=storyboard.time_slot,
                source_fingerprint=storyboard.source_fingerprint,
                created_at=now,
                updated_at=now,
            )
            _, tone_result = find_tone_result(result_id)
            if tone_result is not None:
                tone_result["video_job_id"] = job.video_job_id
            return self._persist_locked(job)

    def run_render(self, video_job_id: str) -> None:
        self._render_lock.acquire()
        try:
            with self._state_lock:
                job = self._get_locked(video_job_id)
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
                storyboard = self._storyboard_builder(processing.result_id)
                if storyboard.source_fingerprint != processing.source_fingerprint:
                    raise WorkflowConflict("원본 광고가 변경되어 다시 생성해야 합니다")

                music_path = None
                music_key = None
                if self._music_catalog is not None:
                    track = self._music_catalog.select_for_tone(processing.tone)
                    music_path = track.path
                    music_key = track.key

                output_path = self._video_dir / f"{video_job_id}.mp4"
                rendered = self._renderer.render(
                    storyboard,
                    output_path=output_path,
                    music_path=music_path,
                )
            except Exception:
                with self._state_lock:
                    failed = self._get_locked(video_job_id).model_copy(
                        update={
                            "render_status": RenderStatus.FAILED,
                            "error_message": "영상 렌더링에 실패했습니다",
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
                        "music_key": music_key,
                        "music_warning": rendered.music_warning,
                        "error_message": None,
                        "updated_at": self._clock(),
                    }
                )
                _, tone_result = find_tone_result(completed.result_id)
                if tone_result is not None:
                    tone_result["video_url"] = completed.video_url
                self._persist_locked(completed)
        finally:
            self._render_lock.release()

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

    def approve(
        self,
        video_job_id: str,
        *,
        activation_at: datetime,
        publish_to_youtube: bool,
        allow_silent: bool,
    ) -> VideoJob:
        with self._state_lock:
            snapshot = self._get_locked(video_job_id)
        if snapshot.render_status is not RenderStatus.COMPLETED:
            raise WorkflowConflict("렌더링 완료 후 승인할 수 있습니다")
        if snapshot.approval_status is ApprovalStatus.REJECTED:
            raise WorkflowConflict("거절된 영상은 승인할 수 없습니다")

        self._validate_schedule(snapshot, activation_at)
        self._validate_integrity(snapshot)
        if snapshot.music_warning and not allow_silent:
            raise WorkflowConflict("음악이 없는 무음 영상을 별도로 확인해야 합니다")

        requested_publish = (
            snapshot.publish_status is not PublishStatus.NOT_REQUESTED
        )
        if snapshot.approval_status is ApprovalStatus.APPROVED:
            if (
                snapshot.activation_at == activation_at
                and requested_publish == publish_to_youtube
                and snapshot.silent_publish_confirmed == bool(
                    snapshot.music_warning and allow_silent
                )
            ):
                return snapshot
            raise WorkflowConflict("승인 후 예약 조건은 변경할 수 없습니다")

        with self._state_lock:
            current = self._get_locked(video_job_id)
            if current.updated_at != snapshot.updated_at:
                raise WorkflowConflict("검토 중 영상 작업 상태가 변경되었습니다")
            approved = current.model_copy(
                update={
                    "approval_status": ApprovalStatus.APPROVED,
                    "publish_status": (
                        PublishStatus.PENDING
                        if publish_to_youtube
                        else PublishStatus.NOT_REQUESTED
                    ),
                    "activation_at": activation_at,
                    "approved_at": self._clock(),
                    "silent_publish_confirmed": bool(
                        current.music_warning and allow_silent
                    ),
                    "youtube_error": None,
                    "updated_at": self._clock(),
                }
            )
            return self._persist_locked(approved)

    def _publish_request(self, job: VideoJob, video_path: Path) -> PublishRequest:
        storyboard = self._storyboard_builder(job.result_id)
        headline = storyboard.scenes[0].text if storyboard.scenes else storyboard.product_name
        title = f"{storyboard.product_name} | {headline}"[:100]
        facts = [scene.text for scene in storyboard.scenes]
        description = "\n\n".join(facts + ["#Shorts"])
        return PublishRequest(
            video_path=video_path,
            title=title,
            description=description,
            tags=("Shorts", "제품광고", storyboard.tone),
            publish_at=job.activation_at,
        )

    def run_publish(self, video_job_id: str) -> None:
        if not self._publish_lock.acquire(blocking=False):
            raise WorkflowConflict("다른 YouTube 게시 작업이 진행 중입니다")
        try:
            with self._state_lock:
                snapshot = self._get_locked(video_job_id)
            if snapshot.approval_status is not ApprovalStatus.APPROVED:
                raise WorkflowConflict("승인된 영상만 게시할 수 있습니다")
            if snapshot.publish_status is not PublishStatus.PENDING:
                raise WorkflowConflict("게시 대기 중인 영상만 업로드할 수 있습니다")
            if snapshot.activation_at is None:
                raise WorkflowConflict("게시 예약 시각이 없습니다")

            try:
                video_path = self._validate_integrity(snapshot)
                request = self._publish_request(snapshot, video_path)
                video_id = self._publisher.publish(request)
            except AuthenticationRequired:
                status = PublishStatus.AUTH_REQUIRED
                error = "YouTube 인증이 필요합니다"
                video_id = None
            except ScheduleExpired:
                status = PublishStatus.SCHEDULE_EXPIRED
                error = "YouTube 예약 시각이 지났습니다"
                video_id = None
            except PublishUncertain:
                status = PublishStatus.NEEDS_REVIEW
                error = "YouTube 게시 결과를 수동으로 확인해야 합니다"
                video_id = None
            except WorkflowConflict:
                status = PublishStatus.NEEDS_REVIEW
                error = "게시 전 영상 무결성을 다시 확인해야 합니다"
                video_id = None
            except PublishRejected:
                status = PublishStatus.FAILED
                error = "YouTube 게시에 실패했습니다"
                video_id = None
            except Exception:
                status = PublishStatus.FAILED
                error = "YouTube 게시에 실패했습니다"
                video_id = None
            else:
                status = PublishStatus.SCHEDULED
                error = None

            with self._state_lock:
                current = self._get_locked(video_job_id)
                if current.updated_at != snapshot.updated_at:
                    raise WorkflowConflict("게시 중 영상 작업 상태가 변경되었습니다")
                updated = current.model_copy(
                    update={
                        "publish_status": status,
                        "youtube_video_id": video_id,
                        "youtube_error": error,
                        "updated_at": self._clock(),
                    }
                )
                self._persist_locked(updated)
        finally:
            self._publish_lock.release()

    def reject(self, video_job_id: str) -> VideoJob:
        with self._state_lock:
            job = self._get_locked(video_job_id)
            if job.approval_status is not ApprovalStatus.PENDING:
                raise WorkflowConflict("검토 대기 중인 영상만 거절할 수 있습니다")
            rejected = job.model_copy(
                update={
                    "approval_status": ApprovalStatus.REJECTED,
                    "updated_at": self._clock(),
                }
            )
            return self._persist_locked(rejected)

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
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials.from_authorized_user_file(
            str(token_path),
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        return build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    return create_service


def build_default_video_workflow() -> VideoWorkflowService:
    repo_root = Path(__file__).resolve().parents[3]
    connection_id = os.getenv(
        "YOUTUBE_CONNECTION_ID",
        "demo_merchant_channel",
    )
    upload_enabled = (
        os.getenv("YOUTUBE_UPLOAD_ENABLED", "false").strip().lower() == "true"
    )
    token_path = _external_file(
        os.getenv("YOUTUBE_TOKEN_FILE", ""),
        repo_root=repo_root,
    )
    client_path = _external_file(
        os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", ""),
        repo_root=repo_root,
    )
    if upload_enabled and token_path is not None and client_path is not None:
        publisher: Publisher = GoogleYouTubePublisher(
            service_factory=_youtube_service_factory(token_path),
            connection_id=connection_id,
            token_available=True,
        )
    else:
        publisher = DisabledPublisher(connection_id)

    asset_root = Path(os.getenv("MUSIC_ASSET_DIR", "assets/music/private"))
    manifest_path = Path(
        os.getenv(
            "MUSIC_MANIFEST_PATH",
            "assets/music/private/manifest.json",
        )
    )
    music_catalog = None
    if manifest_path.is_file():
        try:
            music_catalog = MusicCatalog.load(
                manifest_path,
                asset_root=asset_root,
            )
        except (OSError, ValueError):
            music_catalog = None

    renderer = RushHourVideoRenderer(
        font_path=Path(
            os.getenv(
                "VIDEO_FONT_PATH",
                "assets/fonts/NanumGothic-Regular.ttf",
            )
        ),
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
        preset=os.getenv("VIDEO_FFMPEG_PRESET", "veryfast"),
    )
    return VideoWorkflowService(
        renderer=renderer,
        music_catalog=music_catalog,
        publisher=publisher,
        now=lambda: datetime.now(timezone.utc),
        video_dir=Path(os.getenv("VIDEO_DIR", "data/videos")),
    )
