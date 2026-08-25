from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.backend.services.youtube_publisher import (
    AuthenticationRequired,
    DisabledPublisher,
    GoogleYouTubePublisher,
    PublishRejected,
    PublishRequest,
    PublishUncertain,
    ScheduleExpired,
)


KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=KST)


class FakeInsertRequest:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)

    def next_chunk(self):
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return None, outcome


class FakeVideos:
    def __init__(self, outcomes):
        self._outcomes = outcomes
        self.insert_calls = []

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        return FakeInsertRequest(self._outcomes)


class FakeYouTubeService:
    def __init__(self, outcomes):
        self._videos = FakeVideos(outcomes)

    def videos(self):
        return self._videos


def _http_error(status: int) -> HttpError:
    return HttpError(Response({"status": str(status)}), b"external error")


def _request(video_path: Path, *, publish_at=None) -> PublishRequest:
    return PublishRequest(
        video_path=video_path,
        title="휴대용 선풍기 | 출근길 필수템",
        description="가볍고 시원하게\n\n#Shorts",
        tags=("Shorts", "제품광고"),
        publish_at=publish_at
        or datetime(2026, 8, 10, 8, 0, tzinfo=KST),
    )


def _publisher(service, *, sleep=lambda _: None):
    return GoogleYouTubePublisher(
        service_factory=lambda: service,
        media_factory=lambda *args, **kwargs: {
            "args": args,
            "kwargs": kwargs,
        },
        connection_id="demo_merchant_channel",
        token_available=True,
        now=lambda: NOW,
        sleep=sleep,
    )


def test_publish_body_is_private_and_uses_utc_schedule(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")
    service = FakeYouTubeService([{"id": "yt_123"}])

    video_id = _publisher(service).publish(_request(video))

    body = service._videos.insert_calls[0]["body"]
    assert video_id == "yt_123"
    assert body["status"] == {
        "privacyStatus": "private",
        "publishAt": "2026-08-09T23:00:00Z",
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": True,
    }
    assert body["snippet"]["title"] == "휴대용 선풍기 | 출근길 필수템"
    assert body["snippet"]["tags"] == ["Shorts", "제품광고"]


def test_disabled_publisher_requires_authentication(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")

    with pytest.raises(AuthenticationRequired):
        DisabledPublisher("demo_merchant_channel").publish(_request(video))


def test_missing_video_is_rejected_before_service_creation(tmp_path):
    calls = 0

    def service_factory():
        nonlocal calls
        calls += 1
        return FakeYouTubeService([{"id": "unexpected"}])

    publisher = GoogleYouTubePublisher(
        service_factory=service_factory,
        media_factory=lambda *args, **kwargs: object(),
        connection_id="demo_merchant_channel",
        token_available=True,
        now=lambda: NOW,
        sleep=lambda _: None,
    )

    with pytest.raises(PublishRejected, match="파일"):
        publisher.publish(_request(tmp_path / "missing.mp4"))

    assert calls == 0


def test_naive_publish_time_is_rejected(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")

    with pytest.raises(PublishRejected, match="시간대"):
        _publisher(FakeYouTubeService([{"id": "unexpected"}])).publish(
            _request(video, publish_at=datetime(2026, 8, 10, 8, 0))
        )


def test_past_publish_time_is_not_sent_to_youtube(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")

    with pytest.raises(ScheduleExpired):
        _publisher(FakeYouTubeService([{"id": "unexpected"}])).publish(
            _request(
                video,
                publish_at=datetime(2026, 8, 8, 2, 0, tzinfo=UTC),
            )
        )


def test_retryable_error_retries_without_exceeding_three_attempts(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")
    service = FakeYouTubeService(
        [_http_error(503), _http_error(503), {"id": "yt_after_retry"}]
    )
    sleeps = []

    video_id = _publisher(service, sleep=sleeps.append).publish(_request(video))

    assert video_id == "yt_after_retry"
    assert sleeps == [1.0, 2.0]


def test_exhausted_retryable_error_is_reported_as_uncertain(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")
    service = FakeYouTubeService(
        [_http_error(503), _http_error(503), _http_error(503)]
    )
    sleeps = []

    with pytest.raises(PublishUncertain):
        _publisher(service, sleep=sleeps.append).publish(_request(video))

    assert sleeps == [1.0, 2.0]


def test_non_retryable_bad_request_is_not_retried(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")
    service = FakeYouTubeService([_http_error(400), {"id": "unexpected"}])

    with pytest.raises(PublishRejected):
        _publisher(service).publish(_request(video))

    assert len(service._videos.insert_calls) == 1


def test_status_exposes_connection_without_secret_paths():
    status = _publisher(FakeYouTubeService([{"id": "unused"}])).status()

    assert status.configured is True
    assert status.connection_id == "demo_merchant_channel"
    assert status.token_available is True
