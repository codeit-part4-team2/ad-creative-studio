from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.backend.services import model_server_client
from app.backend.services.storyboard import Storyboard


MAX_SCENE_PIXELS = 20_000_000
NEGATIVE_PROMPT = (
    "text, readable text, letters, pseudo-text, gibberish lettering, numbers, "
    "typography, logo, watermark, signature, price tag, discount badge, menu board, "
    "signboard, poster, product label, packaging text, screen text, user interface, "
    "duplicate product, extra appliance, distorted object, blurry, low resolution, "
    "wristwatch, watch face, clock, timer, dial, secondary product, duplicate appliance, "
    "large circular prop, dominant background object, softbox, tripod, studio light, "
    "photography equipment"
)


@dataclass(frozen=True, slots=True)
class SceneImage:
    purpose: str
    path: Path
    sha256: str
    source: str


@dataclass(frozen=True, slots=True)
class SceneImageSet:
    images: tuple[SceneImage, SceneImage, SceneImage]

    @property
    def sha256s(self) -> tuple[str, str, str]:
        return tuple(image.sha256 for image in self.images)


GenerationRequester = Callable[..., Mapping[str, object]]
GeneratedImageFetcher = Callable[[str], Image.Image]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scene_prompt(*, purpose: str, tone: str, time_slot: str) -> str:
    time_context = "early morning commute" if time_slot == "commute_am" else "evening rush hour"
    purpose_context = {
        "self_aware": (
            "deadpan cinematic studio background, centered negative space, "
            "one restrained spotlight, subtly absurd serious mood"
        ),
        "benefit": (
            "clean small-business advertising set, useful everyday context, "
            "clear depth and premium practical mood"
        ),
    }[purpose]
    return (
        f"9:16 vertical {tone} commercial background for {time_context}, "
        f"{purpose_context}, one unobstructed staging area, "
        "small peripheral props only, all props confined to the far edges, "
        "plain uninterrupted wall behind the staging area, "
        "blank unmarked surfaces, background only, no product, no typography, "
        "no readable text or symbols anywhere"
    )


class SceneImageProvider:
    def __init__(
        self,
        *,
        request_generation: GenerationRequester = model_server_client.request_generation_sync,
        fetch_generated_image: GeneratedImageFetcher = model_server_client.fetch_generated_image_sync,
    ) -> None:
        self._request_generation = request_generation
        self._fetch_generated_image = fetch_generated_image

    @staticmethod
    def _persist_image(image: Image.Image, destination: Path) -> Path:
        rgb_image = image.convert("RGB")
        width, height = rgb_image.size
        if width <= 0 or height <= 0 or width * height > MAX_SCENE_PIXELS:
            raise RuntimeError("쇼츠 장면 이미지 크기가 허용 범위를 벗어났습니다")
        destination.parent.mkdir(parents=True, exist_ok=True)
        rgb_image.save(destination, format="PNG")
        return destination.resolve()

    def _persist_hero(self, storyboard: Storyboard, output_dir: Path) -> SceneImage:
        hero_path = storyboard.image_path.expanduser().resolve()
        if not hero_path.is_file():
            raise RuntimeError("기존 광고 대표 이미지를 찾을 수 없습니다")
        with Image.open(hero_path) as source_image:
            destination = self._persist_image(source_image.copy(), output_dir / "scene_hero.png")
        return SceneImage(
            purpose="hero",
            path=destination,
            sha256=_file_sha256(destination),
            source="existing_result",
        )

    def _generate_scene(
        self,
        *,
        storyboard: Storyboard,
        product_image_url: str,
        purpose: str,
        output_dir: Path,
    ) -> SceneImage:
        response = self._request_generation(
            product_id=storyboard.product_id,
            product_image_url=product_image_url,
            tone=storyboard.tone,
            image_prompt=_scene_prompt(
                purpose=purpose,
                tone=storyboard.tone,
                time_slot=storyboard.time_slot,
            ),
            negative_prompt=NEGATIVE_PROMPT,
            time_slot=storyboard.time_slot,
        )
        if response.get("status") != "done":
            raise RuntimeError("쇼츠 추가 장면 생성에 실패했습니다")
        if response.get("product_preserved") is not True:
            raise RuntimeError("추가 장면의 제품 보존을 확인할 수 없습니다")
        generated_image_url = response.get("generated_image_url")
        if not isinstance(generated_image_url, str) or not generated_image_url.strip():
            raise RuntimeError("추가 장면 이미지 URL이 없습니다")
        image = self._fetch_generated_image(generated_image_url)
        destination = self._persist_image(image, output_dir / f"scene_{purpose}.png")
        return SceneImage(
            purpose=purpose,
            path=destination,
            sha256=_file_sha256(destination),
            source="model_server",
        )

    def build(
        self,
        *,
        storyboard: Storyboard,
        product_image_url: str,
        output_dir: Path,
    ) -> SceneImageSet:
        resolved_output = output_dir.expanduser().resolve()
        resolved_output.mkdir(parents=True, exist_ok=True)
        hero = self._persist_hero(storyboard, resolved_output)
        generated = tuple(
            self._generate_scene(
                storyboard=storyboard,
                product_image_url=product_image_url,
                purpose=purpose,
                output_dir=resolved_output,
            )
            for purpose in ("self_aware", "benefit")
        )
        images = (hero, generated[0], generated[1])
        if len({image.sha256 for image in images}) != 3:
            raise RuntimeError("쇼츠에는 서로 다른 3장의 제품 이미지가 필요합니다")
        if any(not image.path.is_relative_to(resolved_output) for image in images):
            raise RuntimeError("쇼츠 장면 이미지가 작업 디렉터리 밖에 있습니다")
        return SceneImageSet(images=images)
