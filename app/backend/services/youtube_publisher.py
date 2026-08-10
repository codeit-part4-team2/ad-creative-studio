from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


RETRIABLE_STATUS_CODES = {500, 502, 503, 504}


class PublisherError(RuntimeError):
    pass


class AuthenticationRequired(PublisherError):
    pass


class ScheduleExpired(PublisherError):
    pass


class PublishRejected(PublisherError):
    pass


class PublishUncertain(PublisherError):
    pass


@dataclass(frozen=True)
class PublishRequest:
    video_path: Path
    title: str
    description: str
    tags: tuple[str, ...]
    publish_at: datetime


@dataclass(frozen=True)
class PublisherStatus:
    configured: bool
    connection_id: str
    token_available: bool


class Publisher(Protocol):
    def status(self) -> PublisherStatus:
        raise NotImplementedError

    def publish(self, request: PublishRequest) -> str:
        raise NotImplementedError


class DisabledPublisher:
    def __init__(self, connection_id: str) -> None:
        self._connection_id = connection_id

    def status(self) -> PublisherStatus:
        return PublisherStatus(
            configured=False,
            connection_id=self._connection_id,
            token_available=False,
        )

    def publish(self, request: PublishRequest) -> str:
        raise AuthenticationRequired("YouTube 업로드가 설정되지 않았습니다")


class GoogleYouTubePublisher:
    def __init__(
        self,
        *,
        service_factory: Callable[[], object],
        connection_id: str,
        token_available: bool,
        media_factory: Callable[..., object] = MediaFileUpload,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._service_factory = service_factory
        self._connection_id = connection_id
        self._token_available = token_available
        self._media_factory = media_factory
        self._now = now
        self._sleep = sleep

    def status(self) -> PublisherStatus:
        return PublisherStatus(
            configured=self._token_available,
            connection_id=self._connection_id,
            token_available=self._token_available,
        )

    def _validate(self, request: PublishRequest) -> None:
        if not request.video_path.is_file():
            raise PublishRejected("게시할 영상 파일을 찾을 수 없습니다")
        if (
            request.publish_at.tzinfo is None
            or request.publish_at.utcoffset() is None
        ):
            raise PublishRejected("예약 시각에는 시간대 정보가 필요합니다")
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeError("publisher clock must return an aware datetime")
        if request.publish_at <= now:
            raise ScheduleExpired("예약 시각이 이미 지났습니다")

    @staticmethod
    def _publish_at_rfc3339(publish_at: datetime) -> str:
        return (
            publish_at.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    def publish(self, request: PublishRequest) -> str:
        self._validate(request)
        if not self._token_available:
            raise AuthenticationRequired("YouTube 인증 토큰이 필요합니다")

        media = self._media_factory(
            str(request.video_path),
            chunksize=-1,
            resumable=True,
            mimetype="video/mp4",
        )
        body = {
            "snippet": {
                "title": request.title,
                "description": request.description,
                "tags": list(request.tags),
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": self._publish_at_rfc3339(request.publish_at),
                "selfDeclaredMadeForKids": False,
                "containsSyntheticMedia": True,
            },
        }
        try:
            service = self._service_factory()
            upload = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
        except Exception as exc:
            raise AuthenticationRequired(
                "YouTube 인증 서비스를 초기화하지 못했습니다"
            ) from exc

        retry_count = 0
        while True:
            try:
                _, response = upload.next_chunk()
            except HttpError as exc:
                status = int(exc.resp.status)
                if status == 401:
                    raise AuthenticationRequired(
                        "YouTube 인증을 갱신해야 합니다"
                    ) from exc
                if status in RETRIABLE_STATUS_CODES and retry_count < 2:
                    self._sleep(float(2**retry_count))
                    retry_count += 1
                    continue
                raise PublishRejected(
                    f"YouTube 업로드가 거부되었습니다 (HTTP {status})"
                ) from exc
            except OSError as exc:
                raise PublishUncertain(
                    "YouTube 업로드 결과를 확정할 수 없습니다"
                ) from exc

            if response is None:
                continue
            video_id = response.get("id")
            if not video_id:
                raise PublishUncertain(
                    "YouTube 응답에서 영상 ID를 확인할 수 없습니다"
                )
            return str(video_id)
