from pathlib import Path

from PIL import Image, ImageDraw

from app.backend.services.comic_script import ComicLineKind
from app.backend.services.scene_images import SceneImage, SceneImageSet
from app.backend.services.storyboard import StoryboardScene
from app.backend.services.video_renderer import (
    _font_and_lines,
    _make_scene_frame,
    _scene_image_sequence,
)


FONT_PATH = Path("assets/fonts/NanumGothic-Regular.ttf")


def test_caption_layout_is_at_most_two_lines():
    canvas = Image.new("RGB", (1080, 1920), "white")
    draw = ImageDraw.Draw(canvas)

    _font, lines, _spacing = _font_and_lines(
        draw,
        text="주요 특징은 빠른 조리와 간편한 사용입니다.",
        font_path=FONT_PATH,
        max_width=900,
        max_height=210,
    )

    assert 1 <= len(lines) <= 2


def test_caption_has_no_black_panel_behind_text():
    source = Image.new("RGB", (768, 768), "white")
    scene = StoryboardScene(
        "검은 박스 없는 자막입니다.",
        2.0,
        kind=ComicLineKind.INTRO,
        image_purpose="hero",
    )

    frame = _make_scene_frame(
        source=source,
        scene=scene,
        tone="premium",
        font_path=FONT_PATH,
        crop_variant="intro",
    )

    caption_region = frame.crop((100, 120, 980, 360))
    dark_pixels = sum(
        1
        for pixel in caption_region.get_flattened_data()
        if max(pixel) < 80
    )
    assert dark_pixels / (caption_region.width * caption_region.height) < 0.15


def test_three_images_map_to_four_scenes_with_hero_reused_for_cta(tmp_path):
    images = tuple(
        SceneImage(purpose=purpose, path=tmp_path / f"{purpose}.png", sha256=purpose * 8, source="test")
        for purpose in ("hero", "self_aware", "benefit")
    )

    sequence = _scene_image_sequence(SceneImageSet(images=images))

    assert [image.purpose for image in sequence] == ["hero", "self_aware", "benefit", "hero"]
