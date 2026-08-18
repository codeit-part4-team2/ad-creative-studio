from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.backend.services.comic_script import (
    ComicLineKind,
    PronunciationLexicon,
    build_comic_script,
)
from app.backend.services.store import HISTORY, PRODUCTS


RUSH_HOUR_SLOTS = {"commute_am", "commute_pm"}


class StoryboardNotFound(ValueError):
    pass


@dataclass(frozen=True)
class StoryboardScene:
    display_text: str
    duration_sec: float
    spoken_text: str = ""
    kind: ComicLineKind = ComicLineKind.INTRO
    image_purpose: str = "hero"
    accent_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.spoken_text:
            object.__setattr__(self, "spoken_text", self.display_text)

    @property
    def text(self) -> str:
        return self.display_text


@dataclass(frozen=True)
class Storyboard:
    result_id: str
    product_id: str
    tone: str
    time_slot: str
    product_name: str
    image_path: Path
    scenes: tuple[StoryboardScene, ...]
    source_fingerprint: str
    script_version: str = "legacy"
    pronunciation_review_required: bool = False


def find_tone_result(result_id: str) -> tuple[dict | None, dict | None]:
    for entry in HISTORY:
        for tone_result in entry.get("results", []):
            if tone_result.get("result_id") == result_id:
                return entry, tone_result
    return None, None


def _selling_points(product: dict) -> tuple[str, ...]:
    values = product.get("selling_points", [])
    if isinstance(values, str):
        values = [values]
    return tuple(str(value).strip() for value in values if str(value).strip())


def _select_source_image_url(source_image_url: object) -> str:
    if not isinstance(source_image_url, str) or not source_image_url.strip():
        raise ValueError(
            "쇼츠용 무자막 원본 이미지가 없어 광고를 다시 생성해야 합니다"
        )
    normalized_url = source_image_url.strip()
    if not normalized_url.startswith("/files/outputs/"):
        raise ValueError("허용된 출력 경로의 광고 이미지가 필요합니다")
    return normalized_url


def _resolve_image_path(
    image_url: str,
    *,
    output_root: Path,
    static_root: Path,
) -> Path:
    resolved_output_root = output_root.resolve()
    image_path = (
        static_root.resolve() / image_url.removeprefix("/files/")
    ).resolve()
    if not image_path.is_relative_to(resolved_output_root):
        raise ValueError("허용된 출력 경로 밖의 이미지는 사용할 수 없습니다")
    if not image_path.is_file():
        raise ValueError("광고 이미지 파일을 찾을 수 없습니다")
    return image_path


def _fingerprint(
    *,
    product_name: str,
    headline: str,
    subcopy: str,
    selling_points: tuple[str, ...],
    tone: str,
    time_slot: str,
    image_url: str,
    image_path: Path,
    script_version: str,
    script_lines: tuple[tuple[str, str, str], ...],
    pronunciation_review_required: bool,
) -> str:
    payload = {
        "product_name": product_name,
        "headline": headline,
        "subcopy": subcopy,
        "selling_points": selling_points,
        "tone": tone,
        "time_slot": time_slot,
        "image_url": image_url,
        "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "script_version": script_version,
        "script_lines": script_lines,
        "pronunciation_review_required": pronunciation_review_required,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_storyboard(
    result_id: str,
    *,
    output_root: Path = Path("data/outputs"),
    static_root: Path = Path("data"),
) -> Storyboard:
    entry, tone_result = find_tone_result(result_id)
    if entry is None or tone_result is None:
        raise StoryboardNotFound("result_id에 해당하는 생성 결과를 찾을 수 없습니다")

    time_slot = tone_result.get("time_slot")
    if time_slot not in RUSH_HOUR_SLOTS:
        raise ValueError("쇼츠는 출근·퇴근 시간대 결과만 지원합니다")

    product = PRODUCTS.get(entry["product_id"], {})
    product_name = str(product.get("product_name") or "제품")
    headline = str(tone_result["headline"])
    subcopy = str(tone_result["subcopy"])
    selling_points = _selling_points(product)
    image_url = _select_source_image_url(tone_result.get("source_image_url"))
    image_path = _resolve_image_path(
        image_url,
        output_root=output_root,
        static_root=static_root,
    )

    raw_pronunciations = product.get("pronunciations") or {}
    pronunciations = (
        raw_pronunciations if isinstance(raw_pronunciations, dict) else {}
    )
    script = build_comic_script(
        product_name=product_name,
        selling_points=selling_points,
        time_slot=time_slot,
        lexicon=PronunciationLexicon(pronunciations),
    )
    purposes = {
        ComicLineKind.INTRO: "hero",
        ComicLineKind.SELF_AWARE: "self_aware",
        ComicLineKind.BENEFIT: "benefit",
        ComicLineKind.CTA: "cta",
    }
    durations = {
        ComicLineKind.INTRO: 2.5,
        ComicLineKind.SELF_AWARE: 2.5,
        ComicLineKind.BENEFIT: 3.0,
        ComicLineKind.CTA: 3.0,
    }
    scenes = tuple(
        StoryboardScene(
            display_text=line.display_text,
            spoken_text=line.spoken_text,
            kind=line.kind,
            image_purpose=purposes[line.kind],
            duration_sec=durations[line.kind],
            accent_terms=(selling_points[0],)
            if line.kind is ComicLineKind.BENEFIT and selling_points
            else (),
        )
        for line in script.lines
    )

    return Storyboard(
        result_id=result_id,
        product_id=entry["product_id"],
        tone=tone_result["tone"],
        time_slot=time_slot,
        product_name=product_name,
        image_path=image_path,
        scenes=scenes,
        script_version=script.version,
        pronunciation_review_required=(
            script.pronunciation_review_required
        ),
        source_fingerprint=_fingerprint(
            product_name=product_name,
            headline=headline,
            subcopy=subcopy,
            selling_points=selling_points,
            tone=tone_result["tone"],
            time_slot=time_slot,
            image_url=image_url,
            image_path=image_path,
            script_version=script.version,
            script_lines=tuple(
                (line.display_text, line.spoken_text, line.kind.value)
                for line in script.lines
            ),
            pronunciation_review_required=(
                script.pronunciation_review_required
            ),
        ),
    )


def current_source_fingerprint(
    result_id: str,
    *,
    output_root: Path = Path("data/outputs"),
    static_root: Path = Path("data"),
) -> str:
    return build_storyboard(
        result_id,
        output_root=output_root,
        static_root=static_root,
    ).source_fingerprint
