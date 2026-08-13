from pathlib import Path

import pytest
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


@pytest.mark.parametrize(
    ("text", "expected_lines"),
    (
        (
            "휴대용 선풍기, 출근길에 짧게 소개할게요.",
            ["휴대용 선풍기, 출근길에", "짧게 소개할게요."],
        ),
        (
            "주요 특징을 말씀드리면, USB-C 충전입니다.",
            ["주요 특징을 말씀드리면,", "USB-C 충전입니다."],
        ),
    ),
)
def test_caption_wraps_at_spaces_without_splitting_words(text, expected_lines):
    canvas = Image.new("RGB", (1080, 1920), "white")
    draw = ImageDraw.Draw(canvas)

    _font, lines, _spacing = _font_and_lines(
        draw,
        text=text,
        font_path=FONT_PATH,
        max_width=900,
        max_height=210,
    )

    assert lines == expected_lines


def test_overlong_product_caption_uses_two_line_ellipsis_instead_of_failing():
    canvas = Image.new("RGB", (1080, 1920), "white")
    draw = ImageDraw.Draw(canvas)

    font, lines, _spacing = _font_and_lines(
        draw,
        text=(
            "퇴근 중이시라면 프리미엄 초경량 무선 노이즈캔슬링 스마트 "
            "블루투스 이어폰 세트만 보고 가세요."
        ),
        font_path=FONT_PATH,
        max_width=900,
        max_height=210,
    )

    assert len(lines) == 2
    assert lines[-1].endswith("…")
    assert all(
        draw.textbbox((0, 0), line, font=font)[2] <= 900
        for line in lines
    )


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
        font_path=FONT_PATH,
    )

    caption_region = frame.crop((100, 120, 980, 360))
    dark_pixels = sum(
        1
        for pixel in caption_region.get_flattened_data()
        if max(pixel) < 80
    )
    assert dark_pixels / (caption_region.width * caption_region.height) < 0.15


def test_scene_frame_fills_portrait_with_single_unfiltered_image(monkeypatch):
    source_color = (110, 147, 184)
    source = Image.new("RGB", (768, 768), source_color)
    scene = StoryboardScene(
        "전체 화면으로 보여드립니다.",
        2.0,
        kind=ComicLineKind.BENEFIT,
        image_purpose="benefit",
    )

    def reject_filter(*_args, **_kwargs):
        raise AssertionError("scene image must not be blurred")

    monkeypatch.setattr("PIL.Image.Image.filter", reject_filter)

    frame = _make_scene_frame(
        source=source,
        scene=scene,
        font_path=FONT_PATH,
    )

    assert frame.size == (1080, 1920)
    assert frame.getpixel((0, 0)) == source_color
    assert frame.getpixel((1079, 0)) == source_color
    assert frame.getpixel((0, 1919)) == source_color
    assert frame.getpixel((1079, 1919)) == source_color


def test_scene_frame_cover_crop_keeps_centered_product_visible():
    source = Image.new("RGB", (768, 768), "#B94A48")
    source_draw = ImageDraw.Draw(source)
    source_draw.rectangle((300, 0, 468, 768), fill="#356AA0")
    scene = StoryboardScene(
        "제품은 가운데 있습니다.",
        2.0,
        kind=ComicLineKind.BENEFIT,
        image_purpose="benefit",
    )

    frame = _make_scene_frame(
        source=source,
        scene=scene,
        font_path=FONT_PATH,
    )

    assert frame.getpixel((0, 960)) == (185, 74, 72)
    assert frame.getpixel((540, 960)) == (53, 106, 160)
    assert frame.getpixel((1079, 960)) == (185, 74, 72)


def test_three_images_map_to_four_scenes_with_hero_reused_for_cta(tmp_path):
    images = tuple(
        SceneImage(purpose=purpose, path=tmp_path / f"{purpose}.png", sha256=purpose * 8, source="test")
        for purpose in ("hero", "self_aware", "benefit")
    )

    sequence = _scene_image_sequence(SceneImageSet(images=images))

    assert [image.purpose for image in sequence] == ["hero", "self_aware", "benefit", "hero"]
