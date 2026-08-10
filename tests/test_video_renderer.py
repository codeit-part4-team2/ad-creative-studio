import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.backend.services.storyboard import Storyboard, StoryboardScene
from app.backend.services.video_renderer import (
    RushHourVideoRenderer,
    fit_inside,
)


def test_fit_inside_preserves_entire_source_aspect_ratio():
    width, height = fit_inside(
        source_size=(1080, 1350),
        bounds=(980, 1225),
    )

    assert (width, height) == (980, 1225)
    assert width / height == 1080 / 1350


@pytest.mark.parametrize(
    ("time_slot", "headline", "color"),
    [
        ("commute_am", "출근길 필수템", "#315a78"),
        ("commute_pm", "퇴근길 한눈에", "#783f5a"),
    ],
)
def test_renderer_outputs_verified_vertical_mp4_with_silent_aac(
    tmp_path,
    time_slot,
    headline,
    color,
):
    image_path = tmp_path / "card.png"
    Image.new("RGB", (1080, 1350), color).save(image_path)
    board = Storyboard(
        result_id="res_1",
        product_id="prd_1",
        tone="practical",
        time_slot=time_slot,
        product_name="휴대용 선풍기",
        image_path=image_path,
        scenes=(
            StoryboardScene(headline, 2.5),
            StoryboardScene("가볍고 시원하게", 3.0),
            StoryboardScene("휴대용 선풍기\n지금 확인해보세요", 4.5),
        ),
        source_fingerprint="a" * 64,
    )
    output_path = tmp_path / f"video_{time_slot}.mp4"

    result = RushHourVideoRenderer(
        font_path=Path("assets/fonts/NanumGothic-Regular.ttf"),
        preset="ultrafast",
    ).render(
        board,
        output_path=output_path,
        music_path=None,
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
    assert result.output_path == output_path
    assert result.output_path.stat().st_size > 0
    assert result.width == 1080
    assert result.height == 1920
    assert 10.0 <= result.duration_sec <= 10.2
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.music_warning == "music_unavailable"
    assert streams["video"]["width"] == 1080
    assert streams["video"]["height"] == 1920
    assert streams["audio"]["codec_name"] == "aac"
    assert len(result.sha256) == 64
