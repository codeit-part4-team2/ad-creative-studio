from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.backend.schemas.video import VideoApprovalRequest, VideoJob


def test_approval_request_rejects_removed_silent_music_field():
    with pytest.raises(ValidationError):
        VideoApprovalRequest(
            activation_at=datetime(2026, 8, 12, 8, 0, tzinfo=timezone.utc),
            publish_to_youtube=False,
            allow_silent=True,
        )


def test_approval_request_accepts_explicit_pronunciation_confirmation():
    request = VideoApprovalRequest(
        activation_at=datetime(2026, 8, 12, 8, 0, tzinfo=timezone.utc),
        publish_to_youtube=False,
        pronunciation_confirmed=True,
    )

    assert request.pronunciation_confirmed is True


def test_video_job_exposes_tts_and_scene_integrity_without_music_fields():
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    job = VideoJob(
        video_job_id="video_1",
        result_id="res_1",
        product_id="prd_1",
        tone="premium",
        time_slot="commute_pm",
        source_fingerprint="a" * 64,
        script_version="deadpan-ai-v1",
        script_lines=("제품입니다.", "저는 퇴근하지 않습니다."),
        tts_engine="melotts-korean",
        tts_voice_preset="deadpan-ai-v1",
        tts_audio_sha256="b" * 64,
        scene_image_sha256s=("c" * 64, "d" * 64, "e" * 64),
        caption_layout_version="bright-outline-v1",
        created_at=now,
        updated_at=now,
    )

    payload = job.model_dump(mode="json")
    assert payload["tts_audio_sha256"] == "b" * 64
    assert len(payload["scene_image_sha256s"]) == 3
    assert "music_key" not in payload
    assert "music_warning" not in payload
    assert "silent_publish_confirmed" not in payload
