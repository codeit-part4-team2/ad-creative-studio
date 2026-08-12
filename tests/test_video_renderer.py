import hashlib
import json
import math
import subprocess
import wave
from array import array
from pathlib import Path

import pytest
from PIL import Image

from app.backend.services.comic_script import ComicLineKind
from app.backend.services.scene_images import SceneImage, SceneImageSet
from app.backend.services.storyboard import Storyboard, StoryboardScene
from app.backend.services.tts_provider import TTSAudio
from app.backend.services.video_renderer import (
    CAPTION_LAYOUT_VERSION,
    DEADPAN_SILENCE_SEC,
    RushHourVideoRenderer,
    _draw_caption,
    fit_inside,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_voice_wav(path: Path, *, duration_sec: float = 2.1) -> TTSAudio:
    sample_rate = 44_100
    samples = array(
        "h",
        (
            round(5_000 * math.sin(2 * math.pi * 330 * index / sample_rate))
            for index in range(round(sample_rate * duration_sec))
        ),
    )
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    return TTSAudio(
        path=path.resolve(),
        duration_sec=duration_sec,
        sha256=_sha256(path),
        engine="fake-melotts",
        voice_preset="deadpan-ai-v1",
    )


def _scene_images(tmp_path: Path) -> SceneImageSet:
    scene_images: list[SceneImage] = []
    for purpose, color in (("hero", "navy"), ("self_aware", "maroon"), ("benefit", "green")):
        path = tmp_path / f"{purpose}.png"
        Image.new("RGB", (768, 768), color).save(path)
        scene_images.append(
            SceneImage(
                purpose=purpose,
                path=path.resolve(),
                sha256=_sha256(path),
                source="test",
            )
        )
    return SceneImageSet(images=tuple(scene_images))


def _storyboard(tmp_path: Path) -> Storyboard:
    scenes = (
        StoryboardScene("테스트 상품입니다.", 2.0, kind=ComicLineKind.INTRO, image_purpose="hero"),
        StoryboardScene(
            "저는 퇴근을 하지 않습니다.",
            2.0,
            kind=ComicLineKind.SELF_AWARE,
            image_purpose="self_aware",
        ),
        StoryboardScene(
            "주요 특징은 빠른 조리입니다.",
            2.0,
            kind=ComicLineKind.BENEFIT,
            image_purpose="benefit",
            accent_terms=("빠른 조리",),
        ),
        StoryboardScene("퇴근길에 확인해 보세요.", 2.0, kind=ComicLineKind.CTA, image_purpose="cta"),
    )
    return Storyboard(
        result_id="res_1",
        product_id="prd_1",
        tone="premium",
        time_slot="commute_pm",
        product_name="테스트 상품",
        image_path=tmp_path / "unused-legacy-path.png",
        scenes=scenes,
        source_fingerprint="a" * 64,
        script_version="deadpan-ai-v1",
    )


def test_fit_inside_preserves_entire_source_aspect_ratio():
    width, height = fit_inside(
        source_size=(1080, 1350),
        bounds=(980, 1225),
    )

    assert (width, height) == (980, 1225)
    assert width / height == 1080 / 1350


@pytest.mark.parametrize("background", ("white", "#E8E8E8", "#0B1020"))
def test_caption_is_plain_and_readable_without_shadow_or_accent(
    monkeypatch,
    background,
):
    canvas = Image.new("RGBA", (1080, 1920), background)
    scene = StoryboardScene(
        "주요 특징은 빠른 조리입니다.",
        2.0,
        kind=ComicLineKind.BENEFIT,
        image_purpose="benefit",
        accent_terms=("빠른 조리",),
    )

    def reject_blur(*_args, **_kwargs):
        raise AssertionError("caption shadow blur must not be used")

    def reject_box(*_args, **_kwargs):
        raise AssertionError("caption box must not be used")

    monkeypatch.setattr(
        "app.backend.services.video_renderer.ImageFilter.GaussianBlur",
        reject_blur,
    )
    monkeypatch.setattr("PIL.ImageDraw.ImageDraw.rectangle", reject_box)
    monkeypatch.setattr("PIL.ImageDraw.ImageDraw.rounded_rectangle", reject_box)

    _draw_caption(
        canvas,
        scene=scene,
        font_path=Path("assets/fonts/NanumGothic-Regular.ttf"),
    )

    pixels = set(canvas.crop((0, 1500, 1080, 1920)).get_flattened_data())
    assert (248, 250, 252, 255) in pixels
    assert (18, 24, 38, 255) in pixels
    assert (231, 213, 165, 255) not in pixels
    assert CAPTION_LAYOUT_VERSION == "plain-outline-v2"


def test_renderer_outputs_verified_vertical_mp4_with_voiced_aac(tmp_path):
    scene_images = _scene_images(tmp_path)
    speech_audio = tuple(
        _write_voice_wav(tmp_path / f"line-{index}.wav")
        for index in range(4)
    )
    output_path = tmp_path / "comic-short.mp4"

    result = RushHourVideoRenderer(
        font_path=Path("assets/fonts/NanumGothic-Regular.ttf"),
        preset="ultrafast",
    ).render(
        _storyboard(tmp_path),
        scene_images=scene_images,
        speech_audio=speech_audio,
        output_path=output_path,
    )

    probe = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        ).stdout
    )
    streams = {stream["codec_type"]: stream for stream in probe["streams"]}
    assert result.output_path == output_path.resolve()
    assert result.output_path.stat().st_size > 0
    assert result.width == 1080
    assert result.height == 1920
    assert 9.95 <= result.duration_sec <= 10.3
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.caption_layout_version == CAPTION_LAYOUT_VERSION
    assert result.scene_image_sha256s == scene_images.sha256s
    assert len(result.tts_audio_sha256) == 64
    assert streams["video"]["width"] == 1080
    assert streams["video"]["height"] == 1920
    assert streams["audio"]["codec_name"] == "aac"
    assert DEADPAN_SILENCE_SEC == 0.5


def test_renderer_rejects_invalid_estimated_duration_before_ffmpeg(tmp_path):
    class NoFfmpegRenderer(RushHourVideoRenderer):
        def __init__(self) -> None:
            super().__init__(font_path=Path("assets/fonts/NanumGothic-Regular.ttf"))
            self.run_count = 0

        def _run(self, args: list[str]) -> None:
            self.run_count += 1
            raise AssertionError(f"FFmpeg must not run for invalid duration: {args}")

    renderer = NoFfmpegRenderer()
    speech_audio = tuple(
        _write_voice_wav(tmp_path / f"short-{index}.wav", duration_sec=0.1)
        for index in range(4)
    )

    with pytest.raises(RuntimeError, match="10~15"):
        renderer.render(
            _storyboard(tmp_path),
            scene_images=_scene_images(tmp_path),
            speech_audio=speech_audio,
            output_path=tmp_path / "must-not-exist.mp4",
        )

    assert renderer.run_count == 0
    assert not (tmp_path / "must-not-exist.mp4").exists()
