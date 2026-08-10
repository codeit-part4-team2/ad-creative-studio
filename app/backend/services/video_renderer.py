from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.backend.services.storyboard import Storyboard, StoryboardScene


VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
TEXT_BOUNDS = (86, 192, 994, 1632)

TONE_ACCENTS = {
    "emotional": "#FFD2C2",
    "modern": "#A8E6FF",
    "practical": "#FFF08A",
    "premium": "#E7D5A5",
}


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    sha256: str
    duration_sec: float
    width: int
    height: int
    video_codec: str
    audio_codec: str
    music_warning: str | None


def fit_inside(
    source_size: tuple[int, int],
    bounds: tuple[int, int],
) -> tuple[int, int]:
    source_width, source_height = source_size
    bound_width, bound_height = bounds
    if min(source_width, source_height, bound_width, bound_height) <= 0:
        raise ValueError("image dimensions must be positive")
    scale = min(bound_width / source_width, bound_height / source_height)
    return round(source_width * scale), round(source_height * scale)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for character in paragraph:
            candidate = current + character
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if current and bbox[2] - bbox[0] > max_width:
                lines.append(current.rstrip())
                current = character.lstrip()
            else:
                current = candidate
        lines.append(current.rstrip())
    return [line for line in lines if line]


def _font_and_lines(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font_path: Path,
    max_width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    for size in range(80, 43, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap_text(draw, text, font, max_width)
        spacing = max(12, size // 4)
        bbox = draw.multiline_textbbox(
            (0, 0),
            "\n".join(lines),
            font=font,
            spacing=spacing,
            align="center",
        )
        if bbox[3] - bbox[1] <= max_height and len(lines) <= 3:
            return font, lines, spacing
    raise ValueError("자막이 안전 영역 안에 들어가지 않습니다")


def _make_scene_frame(
    *,
    source: Image.Image,
    scene: StoryboardScene,
    tone: str,
    font_path: Path,
) -> Image.Image:
    background = ImageOps.fit(
        source.convert("RGB"),
        (VIDEO_WIDTH, VIDEO_HEIGHT),
        method=Image.Resampling.LANCZOS,
    ).filter(ImageFilter.GaussianBlur(radius=36))
    dark_overlay = Image.new(
        "RGBA",
        (VIDEO_WIDTH, VIDEO_HEIGHT),
        (0, 0, 0, 80),
    )
    canvas = Image.alpha_composite(background.convert("RGBA"), dark_overlay)

    foreground_size = fit_inside(source.size, (980, 1225))
    foreground = source.convert("RGBA").resize(
        foreground_size,
        Image.Resampling.LANCZOS,
    )
    foreground_x = (VIDEO_WIDTH - foreground.width) // 2
    foreground_y = 430 + (1225 - foreground.height) // 2
    canvas.alpha_composite(foreground, (foreground_x, foreground_y))

    draw = ImageDraw.Draw(canvas, "RGBA")
    left, top, right, _ = TEXT_BOUNDS
    font, lines, spacing = _font_and_lines(
        draw,
        text=scene.text,
        font_path=font_path,
        max_width=right - left - 72,
        max_height=220,
    )
    rendered_text = "\n".join(lines)
    text_bbox = draw.multiline_textbbox(
        (0, 0),
        rendered_text,
        font=font,
        spacing=spacing,
        align="center",
    )
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    panel_left = max(left, (VIDEO_WIDTH - text_width) // 2 - 36)
    panel_right = min(right, (VIDEO_WIDTH + text_width) // 2 + 36)
    panel_top = top
    panel_bottom = panel_top + text_height + 56
    draw.rounded_rectangle(
        (panel_left, panel_top, panel_right, panel_bottom),
        radius=28,
        fill=(0, 0, 0, 188),
        outline=TONE_ACCENTS.get(tone, "#FFFFFF"),
        width=3,
    )
    draw.multiline_text(
        (VIDEO_WIDTH // 2, panel_top + 28),
        rendered_text,
        font=font,
        fill="white",
        anchor="ma",
        align="center",
        spacing=spacing,
        stroke_width=1,
        stroke_fill=(0, 0, 0, 220),
    )
    return canvas.convert("RGB")


class RushHourVideoRenderer:
    def __init__(
        self,
        *,
        font_path: Path,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        preset: str = "veryfast",
    ) -> None:
        self._font_path = font_path
        self._ffmpeg_bin = ffmpeg_bin
        self._ffprobe_bin = ffprobe_bin
        self._preset = preset

    def _run(self, args: list[str]) -> None:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip()[-1200:]
            raise RuntimeError(f"FFmpeg 처리 실패: {detail}")

    def _write_segment(
        self,
        frame_path: Path,
        segment_path: Path,
        duration_sec: float,
    ) -> None:
        frame_count = round(duration_sec * VIDEO_FPS)
        zoom_step = 0.015 / max(frame_count, 1)
        zoompan = (
            f"zoompan=z='min(zoom+{zoom_step:.8f},1.015)':"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS},"
            "format=yuv420p"
        )
        self._run(
            [
                self._ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-i",
                str(frame_path),
                "-vf",
                zoompan,
                "-frames:v",
                str(frame_count),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                self._preset,
                "-pix_fmt",
                "yuv420p",
                str(segment_path),
            ]
        )

    def _concat_segments(
        self,
        segment_paths: list[Path],
        concat_path: Path,
        output_path: Path,
    ) -> None:
        entries = []
        for path in segment_paths:
            normalized = path.resolve().as_posix().replace("'", r"'\''")
            entries.append(f"file '{normalized}'")
        concat_path.write_text("\n".join(entries), encoding="utf-8")
        self._run(
            [
                self._ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                str(output_path),
            ]
        )

    def _mux_audio(
        self,
        video_only: Path,
        output_path: Path,
        *,
        music_path: Path | None,
        duration_sec: float,
    ) -> str | None:
        common = [
            self._ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_only),
        ]
        if music_path is None or not music_path.is_file():
            self._run(
                common
                + [
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-t",
                    f"{duration_sec:.3f}",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
            )
            return "music_unavailable"

        fade_out_at = max(duration_sec - 0.5, 0.0)
        audio_filter = (
            "loudnorm=I=-16:TP=-1.5:LRA=11,"
            "afade=t=in:st=0:d=0.5,"
            f"afade=t=out:st={fade_out_at:.3f}:d=0.5,"
            f"atrim=duration={duration_sec:.3f}"
        )
        self._run(
            common
            + [
                "-stream_loop",
                "-1",
                "-i",
                str(music_path),
                "-t",
                f"{duration_sec:.3f}",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-filter:a",
                audio_filter,
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        return None

    def _probe(self, output_path: Path) -> dict[str, object]:
        completed = subprocess.run(
            [
                self._ffprobe_bin,
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
            timeout=30,
        )
        payload = json.loads(completed.stdout)
        streams = {
            stream["codec_type"]: stream for stream in payload["streams"]
        }
        video = streams.get("video")
        audio = streams.get("audio")
        if video is None or audio is None:
            raise RuntimeError("완성 영상에 비디오와 오디오 스트림이 모두 필요합니다")
        return {
            "duration_sec": float(payload["format"]["duration"]),
            "width": int(video["width"]),
            "height": int(video["height"]),
            "video_codec": str(video["codec_name"]),
            "audio_codec": str(audio["codec_name"]),
        }

    @staticmethod
    def _validate_probe(metadata: dict[str, object]) -> None:
        if (metadata["width"], metadata["height"]) != (
            VIDEO_WIDTH,
            VIDEO_HEIGHT,
        ):
            raise RuntimeError("완성 영상 해상도가 1080x1920이 아닙니다")
        duration = float(metadata["duration_sec"])
        if not 9.95 <= duration <= 15.05:
            raise RuntimeError("완성 영상 길이가 10~15초 범위를 벗어났습니다")
        if metadata["video_codec"] != "h264":
            raise RuntimeError("완성 영상 코덱이 H.264가 아닙니다")
        if metadata["audio_codec"] != "aac":
            raise RuntimeError("완성 오디오 코덱이 AAC가 아닙니다")

    def render(
        self,
        storyboard: Storyboard,
        *,
        output_path: Path,
        music_path: Path | None,
    ) -> RenderResult:
        if not self._font_path.is_file():
            raise ValueError("한글 폰트 파일을 찾을 수 없습니다")
        if not storyboard.image_path.is_file():
            raise ValueError("광고 이미지 파일을 찾을 수 없습니다")
        duration_sec = sum(scene.duration_sec for scene in storyboard.scenes)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix="rush-hour-video-",
            dir=output_path.parent,
        ) as temporary:
            temp_dir = Path(temporary)
            source = Image.open(storyboard.image_path).convert("RGB")
            segment_paths: list[Path] = []
            for index, scene in enumerate(storyboard.scenes):
                frame_path = temp_dir / f"frame-{index:02d}.png"
                segment_path = temp_dir / f"segment-{index:02d}.mp4"
                frame = _make_scene_frame(
                    source=source,
                    scene=scene,
                    tone=storyboard.tone,
                    font_path=self._font_path,
                )
                frame.save(frame_path)
                self._write_segment(
                    frame_path,
                    segment_path,
                    scene.duration_sec,
                )
                segment_paths.append(segment_path)

            video_only = temp_dir / "video-only.mp4"
            self._concat_segments(
                segment_paths,
                temp_dir / "concat.txt",
                video_only,
            )
            music_warning = self._mux_audio(
                video_only,
                output_path,
                music_path=music_path,
                duration_sec=duration_sec,
            )

        metadata = self._probe(output_path)
        self._validate_probe(metadata)
        return RenderResult(
            output_path=output_path,
            sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            duration_sec=float(metadata["duration_sec"]),
            width=int(metadata["width"]),
            height=int(metadata["height"]),
            video_codec=str(metadata["video_codec"]),
            audio_codec=str(metadata["audio_codec"]),
            music_warning=music_warning,
        )
