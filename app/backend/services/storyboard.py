from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.backend.services.store import HISTORY, PRODUCTS


RUSH_HOUR_SLOTS = {"commute_am", "commute_pm"}


class StoryboardNotFound(ValueError):
    pass


@dataclass(frozen=True)
class StoryboardScene:
    text: str
    duration_sec: float
    accent_terms: tuple[str, ...] = ()


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


def _select_image_url(images: dict[str, str]) -> str:
    image_url = images.get("sns_card") or images.get("thumbnail")
    if image_url is None and images:
        image_url = next(iter(images.values()))
    if not image_url or not image_url.startswith("/files/outputs/"):
        raise ValueError("허용된 출력 경로의 광고 이미지가 필요합니다")
    return image_url


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
    image_url = _select_image_url(tone_result.get("images") or {})
    image_path = _resolve_image_path(
        image_url,
        output_root=output_root,
        static_root=static_root,
    )

    scenes = [
        StoryboardScene(headline, 2.5),
        StoryboardScene(subcopy, 3.0),
    ]
    if selling_points:
        scenes.append(
            StoryboardScene(
                " · ".join(selling_points[:2]),
                4.0,
                selling_points[:2],
            )
        )
        call_to_action_duration = 3.0
    else:
        call_to_action_duration = 4.5
    scenes.append(
        StoryboardScene(
            f"{product_name}\n지금 확인해보세요",
            call_to_action_duration,
        )
    )

    return Storyboard(
        result_id=result_id,
        product_id=entry["product_id"],
        tone=tone_result["tone"],
        time_slot=time_slot,
        product_name=product_name,
        image_path=image_path,
        scenes=tuple(scenes),
        source_fingerprint=_fingerprint(
            product_name=product_name,
            headline=headline,
            subcopy=subcopy,
            selling_points=selling_points,
            tone=tone_result["tone"],
            time_slot=time_slot,
            image_url=image_url,
            image_path=image_path,
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
