from pathlib import Path

import pytest
from PIL import Image

from app.backend.services.comic_script import ComicLineKind
from app.backend.services.scene_images import SceneImageProvider
from app.backend.services.storyboard import Storyboard, StoryboardScene


def _storyboard(tmp_path: Path) -> Storyboard:
    hero_path = tmp_path / "hero.png"
    Image.new("RGB", (64, 64), "navy").save(hero_path)
    scenes = (
        StoryboardScene("제품입니다.", 2.0, kind=ComicLineKind.INTRO, image_purpose="hero"),
        StoryboardScene(
            "저는 퇴근하지 않습니다.",
            2.0,
            kind=ComicLineKind.SELF_AWARE,
            image_purpose="self_aware",
        ),
        StoryboardScene("빠른 조리입니다.", 2.0, kind=ComicLineKind.BENEFIT, image_purpose="benefit"),
        StoryboardScene("확인해 보세요.", 2.0, kind=ComicLineKind.CTA, image_purpose="cta"),
    )
    return Storyboard(
        result_id="res_1",
        product_id="prd_1",
        tone="premium",
        time_slot="commute_pm",
        product_name="전자레인지",
        image_path=hero_path,
        scenes=scenes,
        source_fingerprint="fingerprint",
    )


def test_provider_reuses_hero_and_makes_exactly_two_sequential_calls(tmp_path):
    events: list[str] = []
    prompts: list[str] = []

    def request_generation(**kwargs):
        call_number = len(prompts) + 1
        events.append(f"request:{call_number}")
        prompts.append(kwargs["image_prompt"])
        return {
            "status": "done",
            "generated_image_url": f"/files/outputs/scene-{call_number}.png",
            "product_preserved": True,
        }

    def fetch_image(url: str):
        events.append(f"fetch:{Path(url).stem[-1]}")
        color = "red" if "scene-1" in url else "green"
        return Image.new("RGB", (64, 64), color)

    output_dir = tmp_path / "job"
    images = SceneImageProvider(
        request_generation=request_generation,
        fetch_generated_image=fetch_image,
    ).build(
        storyboard=_storyboard(tmp_path),
        product_image_url="/files/uploads/prd_1.png",
        output_dir=output_dir,
    )

    assert events == ["request:1", "fetch:1", "request:2", "fetch:2"]
    assert len(prompts) == 2
    assert prompts[0] != prompts[1]
    assert [image.purpose for image in images.images] == ["hero", "self_aware", "benefit"]
    assert all(image.path.is_relative_to(output_dir.resolve()) for image in images.images)
    assert len(set(images.sha256s)) == 3


def test_provider_passes_existing_infer_contract_fields(tmp_path):
    calls: list[dict[str, object]] = []

    def request_generation(**kwargs):
        calls.append(kwargs)
        return {
            "status": "done",
            "generated_image_url": f"/files/outputs/{len(calls)}.png",
            "product_preserved": True,
        }

    colors = iter(("red", "green"))
    SceneImageProvider(
        request_generation=request_generation,
        fetch_generated_image=lambda _url: Image.new("RGB", (64, 64), next(colors)),
    ).build(
        storyboard=_storyboard(tmp_path),
        product_image_url="/files/uploads/prd_1.png",
        output_dir=tmp_path / "job",
    )

    assert len(calls) == 2
    assert all(
        set(call) == {
            "product_id",
            "product_image_url",
            "tone",
            "image_prompt",
            "negative_prompt",
            "time_slot",
        }
        for call in calls
    )
    assert all(call["product_id"] == "prd_1" for call in calls)
    assert all(call["time_slot"] == "commute_pm" for call in calls)
    for call in calls:
        negative_prompt = str(call["negative_prompt"])
        assert "wristwatch" in negative_prompt
        assert "large circular prop" in negative_prompt
        assert "softbox" in negative_prompt
        assert "photography equipment" in negative_prompt
        assert "readable text" in negative_prompt
        assert "pseudo-text" in negative_prompt
        assert "numbers" in negative_prompt
        assert "price tag" in negative_prompt
        assert "signboard" in negative_prompt
        assert "poster" in negative_prompt
        assert "user interface" in negative_prompt
        assert "watermark" in negative_prompt
        assert "signature" in negative_prompt
        image_prompt = str(call["image_prompt"])
        assert "unobstructed staging area" in image_prompt
        assert "small peripheral props only" in image_prompt
        assert "blank unmarked surfaces" in image_prompt
        assert "no readable text or symbols anywhere" in image_prompt


def test_provider_fails_closed_when_product_is_not_preserved(tmp_path):
    provider = SceneImageProvider(
        request_generation=lambda **_kwargs: {
            "status": "done",
            "generated_image_url": "/files/outputs/fail.png",
            "product_preserved": False,
        },
        fetch_generated_image=lambda _url: Image.new("RGB", (64, 64), "red"),
    )

    with pytest.raises(RuntimeError, match="제품 보존"):
        provider.build(
            storyboard=_storyboard(tmp_path),
            product_image_url="/files/uploads/prd_1.png",
            output_dir=tmp_path / "job",
        )


def test_provider_rejects_duplicate_scene_images(tmp_path):
    call_count = 0

    def request_generation(**_kwargs):
        nonlocal call_count
        call_count += 1
        return {
            "status": "done",
            "generated_image_url": f"/files/outputs/{call_count}.png",
            "product_preserved": True,
        }

    provider = SceneImageProvider(
        request_generation=request_generation,
        fetch_generated_image=lambda _url: Image.new("RGB", (64, 64), "red"),
    )

    with pytest.raises(RuntimeError, match="서로 다른 3장"):
        provider.build(
            storyboard=_storyboard(tmp_path),
            product_image_url="/files/uploads/prd_1.png",
            output_dir=tmp_path / "job",
        )
