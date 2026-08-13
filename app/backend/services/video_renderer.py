from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.backend.services.comic_script import ComicLineKind
from app.backend.services.scene_images import SceneImage, SceneImageSet
from app.backend.services.storyboard import Storyboard, StoryboardScene
from app.backend.services.tts_provider import TTSAudio


VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
CAPTION_LAYOUT_VERSION = "plain-outline-v2"
BASE_SILENCE_SEC = 0.1
DEADPAN_SILENCE_SEC = 0.5
MIN_VIDEO_DURATION_SEC = 9.95
MAX_VIDEO_DURATION_SEC = 15.05

@dataclass(frozen=True, slots=True)
class RenderResult:
    output_path: Path
    sha256: str
    duration_sec: float
    width: int
    height: int
    video_codec: str
    audio_codec: str
    tts_audio_sha256: str
    scene_image_sha256s: tuple[str, str, str]
    caption_layout_version: str


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scene_silence_sec(scene: StoryboardScene) -> float:
    if scene.kind is ComicLineKind.SELF_AWARE:
        return DEADPAN_SILENCE_SEC
    return BASE_SILENCE_SEC


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
    def fits(value: str) -> bool:
        bbox = draw.textbbox((0, 0), value, font=font)
        return bbox[2] - bbox[0] <= max_width

    def split_oversized_word(word: str) -> list[str]:
        chunks: list[str] = []
        current = ""
        for character in word:
            candidate = current + character
            if current and not fits(candidate):
                chunks.append(current)
                current = character
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}" if current else word
            if fits(candidate):
                current = candidate
                continue

            if current:
                lines.append(current)

            if fits(word):
                current = word
            else:
                chunks = split_oversized_word(word)
                lines.extend(chunks[:-1])
                current = chunks[-1]
        if current:
            lines.append(current)
    return lines


def _font_and_lines(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font_path: Path,
    max_width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    fallback: tuple[ImageFont.FreeTypeFont, list[str], int] | None = None
    for size in range(78, 41, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap_text(draw, text, font, max_width)
        spacing = max(10, size // 5)
        fallback = (font, lines, spacing)
        bbox = draw.multiline_textbbox(
            (0, 0),
            "\n".join(lines),
            font=font,
            spacing=spacing,
            align="center",
            stroke_width=2,
        )
        if bbox[3] - bbox[1] <= max_height and 1 <= len(lines) <= 2:
            return font, lines, spacing

    if fallback is not None:
        font, lines, spacing = fallback
        if len(lines) > 2:
            visible_lines = lines[:2]
            final_words = visible_lines[-1].split()
            while final_words:
                candidate = f"{' '.join(final_words)}…"
                bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=2)
                if bbox[2] - bbox[0] <= max_width:
                    visible_lines[-1] = candidate
                    return font, visible_lines, spacing
                final_words.pop()

            final_line = visible_lines[-1]
            while final_line:
                candidate = f"{final_line}…"
                bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=2)
                if bbox[2] - bbox[0] <= max_width:
                    visible_lines[-1] = candidate
                    return font, visible_lines, spacing
                final_line = final_line[:-1]
    raise ValueError("자막이 2줄 안전 영역 안에 들어가지 않습니다")


def _draw_caption(
    canvas: Image.Image,
    *,
    scene: StoryboardScene,
    font_path: Path,
) -> None:
    base_draw = ImageDraw.Draw(canvas, "RGBA")
    font, lines, spacing = _font_and_lines(
        base_draw,
        text=scene.display_text,
        font_path=font_path,
        max_width=900,
        max_height=210,
    )
    line_boxes = [base_draw.textbbox((0, 0), line, font=font, stroke_width=2) for line in lines]
    line_heights = [box[3] - box[1] for box in line_boxes]
    block_height = sum(line_heights) + spacing * (len(lines) - 1)
    if scene.kind in {ComicLineKind.INTRO, ComicLineKind.SELF_AWARE}:
        current_y = 145
    else:
        current_y = VIDEO_HEIGHT - 145 - block_height

    positions: list[tuple[float, float]] = []
    for line, line_height in zip(lines, line_heights, strict=True):
        line_width = base_draw.textlength(line, font=font)
        line_x = (VIDEO_WIDTH - line_width) / 2
        positions.append((line_x, current_y))
        current_y += line_height + spacing

    draw = ImageDraw.Draw(canvas, "RGBA")
    for line, (line_x, line_y) in zip(lines, positions, strict=True):
        draw.text(
            (line_x, line_y),
            line,
            font=font,
            fill="#F8FAFC",
            stroke_width=2,
            stroke_fill="#121826",
        )


def _make_scene_frame(
    *,
    source: Image.Image,
    scene: StoryboardScene,
    font_path: Path,
    crop_variant: str,
) -> Image.Image:
    background = ImageOps.fit(
        source.convert("RGB"),
        (VIDEO_WIDTH, VIDEO_HEIGHT),
        method=Image.Resampling.LANCZOS,
    ).filter(ImageFilter.GaussianBlur(radius=30))
    canvas = background.convert("RGBA")
    canvas.alpha_composite(
        Image.new("RGBA", canvas.size, (10, 16, 28, 68))
    )

    if crop_variant == "cta":
        foreground = ImageOps.fit(
            source.convert("RGBA"),
            (1010, 1320),
            method=Image.Resampling.LANCZOS,
        )
        foreground_y = 300
    else:
        foreground_size = fit_inside(source.size, (980, 1220))
        foreground = source.convert("RGBA").resize(
            foreground_size,
            Image.Resampling.LANCZOS,
        )
        foreground_y = 350 + (1220 - foreground.height) // 2
    foreground_x = (VIDEO_WIDTH - foreground.width) // 2
    canvas.alpha_composite(foreground, (foreground_x, foreground_y))
    _draw_caption(canvas, scene=scene, font_path=font_path)
    return canvas.convert("RGB")


def _scene_image_sequence(
    scene_images: SceneImageSet,
) -> tuple[SceneImage, SceneImage, SceneImage, SceneImage]:
    if len(scene_images.images) != 3 or len(set(scene_images.sha256s)) != 3:
        raise ValueError("렌더링에는 서로 다른 장면 이미지 3장이 필요합니다")
    by_purpose = {image.purpose: image for image in scene_images.images}
    if set(by_purpose) != {"hero", "self_aware", "benefit"}:
        raise ValueError("hero, self_aware, benefit 장면 이미지가 필요합니다")
    return (
        by_purpose["hero"],
        by_purpose["self_aware"],
        by_purpose["benefit"],
        by_purpose["hero"],
    )


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
            timeout=240,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip()[-1600:]
            raise RuntimeError(f"FFmpeg 처리 실패: {detail}")

    def _write_segment(
        self,
        *,
        frame_path: Path,
        speech_path: Path,
        segment_path: Path,
        speech_duration_sec: float,
        silence_sec: float,
    ) -> None:
        segment_duration = speech_duration_sec + 2 * silence_sec
        audio_filter = (
            f"[1:a]atrim=duration={silence_sec:.3f},asetpts=PTS-STARTPTS[pre];"
            "[2:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono,"
            "asetpts=PTS-STARTPTS[voice];"
            f"[3:a]atrim=duration={silence_sec:.3f},asetpts=PTS-STARTPTS[post];"
            "[pre][voice][post]concat=n=3:v=0:a=1,aresample=44100[audio]"
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
                "-framerate",
                str(VIDEO_FPS),
                "-i",
                str(frame_path),
                "-f",
                "lavfi",
                "-t",
                f"{silence_sec:.3f}",
                "-i",
                "anullsrc=channel_layout=mono:sample_rate=44100",
                "-i",
                str(speech_path),
                "-f",
                "lavfi",
                "-t",
                f"{silence_sec:.3f}",
                "-i",
                "anullsrc=channel_layout=mono:sample_rate=44100",
                "-filter_complex",
                audio_filter,
                "-map",
                "0:v:0",
                "-map",
                "[audio]",
                "-t",
                f"{segment_duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                self._preset,
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(VIDEO_FPS),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "44100",
                "-ac",
                "1",
                "-shortest",
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
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )

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
        streams = {stream["codec_type"]: stream for stream in payload["streams"]}
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
        if (metadata["width"], metadata["height"]) != (VIDEO_WIDTH, VIDEO_HEIGHT):
            raise RuntimeError("완성 영상 해상도가 1080x1920이 아닙니다")
        duration = float(metadata["duration_sec"])
        if not MIN_VIDEO_DURATION_SEC <= duration <= MAX_VIDEO_DURATION_SEC:
            raise RuntimeError("완성 영상 길이가 10~15초 범위를 벗어났습니다")
        if metadata["video_codec"] != "h264":
            raise RuntimeError("완성 영상 코덱이 H.264가 아닙니다")
        if metadata["audio_codec"] != "aac":
            raise RuntimeError("완성 오디오 코덱이 AAC가 아닙니다")

    @staticmethod
    def _validate_speech_audio(
        storyboard: Storyboard,
        speech_audio: tuple[TTSAudio, ...],
    ) -> str:
        if len(storyboard.scenes) != 4 or len(speech_audio) != 4:
            raise ValueError("4개 장면과 4개 TTS 음성이 필요합니다")
        aggregate = hashlib.sha256()
        for audio in speech_audio:
            if not audio.path.is_file() or _file_sha256(audio.path) != audio.sha256:
                raise ValueError("TTS 음성 파일 무결성을 확인할 수 없습니다")
            if audio.duration_sec <= 0:
                raise ValueError("TTS 음성 길이가 올바르지 않습니다")
            aggregate.update(audio.sha256.encode("ascii"))
        return aggregate.hexdigest()

    @staticmethod
    def _validate_estimated_duration(
        storyboard: Storyboard,
        speech_audio: tuple[TTSAudio, ...],
    ) -> None:
        estimated_duration = sum(
            audio.duration_sec + 2 * _scene_silence_sec(scene)
            for scene, audio in zip(
                storyboard.scenes,
                speech_audio,
                strict=True,
            )
        )
        if not MIN_VIDEO_DURATION_SEC <= estimated_duration <= MAX_VIDEO_DURATION_SEC:
            raise RuntimeError("완성 영상 길이가 10~15초 범위를 벗어났습니다")

    def render(
        self,
        storyboard: Storyboard,
        *,
        scene_images: SceneImageSet,
        speech_audio: tuple[TTSAudio, ...],
        output_path: Path,
    ) -> RenderResult:
        if not self._font_path.is_file():
            raise ValueError("한글 폰트 파일을 찾을 수 없습니다")
        tts_audio_sha256 = self._validate_speech_audio(storyboard, speech_audio)
        self._validate_estimated_duration(storyboard, speech_audio)
        image_sequence = _scene_image_sequence(scene_images)
        for scene_image in scene_images.images:
            if not scene_image.path.is_file() or _file_sha256(scene_image.path) != scene_image.sha256:
                raise ValueError("장면 이미지 무결성을 확인할 수 없습니다")

        resolved_output = output_path.expanduser().resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="rush-hour-video-",
            dir=resolved_output.parent,
        ) as temporary:
            temp_dir = Path(temporary)
            segment_paths: list[Path] = []
            for index, (scene, scene_image, audio) in enumerate(
                zip(storyboard.scenes, image_sequence, speech_audio, strict=True)
            ):
                frame_path = temp_dir / f"frame-{index:02d}.png"
                segment_path = temp_dir / f"segment-{index:02d}.mp4"
                with Image.open(scene_image.path) as source_image:
                    frame = _make_scene_frame(
                        source=source_image.copy(),
                        scene=scene,
                        font_path=self._font_path,
                        crop_variant="cta" if index == 3 else "intro",
                    )
                frame.save(frame_path)
                self._write_segment(
                    frame_path=frame_path,
                    speech_path=audio.path,
                    segment_path=segment_path,
                    speech_duration_sec=audio.duration_sec,
                    silence_sec=_scene_silence_sec(scene),
                )
                segment_paths.append(segment_path)
            self._concat_segments(
                segment_paths,
                temp_dir / "concat.txt",
                resolved_output,
            )

        metadata = self._probe(resolved_output)
        self._validate_probe(metadata)
        return RenderResult(
            output_path=resolved_output,
            sha256=_file_sha256(resolved_output),
            duration_sec=float(metadata["duration_sec"]),
            width=int(metadata["width"]),
            height=int(metadata["height"]),
            video_codec=str(metadata["video_codec"]),
            audio_codec=str(metadata["audio_codec"]),
            tts_audio_sha256=tts_audio_sha256,
            scene_image_sha256s=scene_images.sha256s,
            caption_layout_version=CAPTION_LAYOUT_VERSION,
        )
