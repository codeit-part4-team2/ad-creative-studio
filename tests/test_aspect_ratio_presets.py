from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.backend.schemas.generation import GenerationRequest
from app.image_presets import get_image_preset


@pytest.mark.parametrize(
    ("key", "background", "composite", "export"),
    [
        ("thumbnail", (768, 768), (1024, 1024), (1080, 1080)),
        ("sns_card", (672, 840), (896, 1120), (1080, 1350)),
        ("story_vertical", (576, 1024), (720, 1280), (1080, 1920)),
        ("wide_banner", (1024, 576), (1280, 720), (1280, 720)),
    ],
)
def test_image_preset_dimensions_preserve_the_advertising_ratio(
    key: str,
    background: tuple[int, int],
    composite: tuple[int, int],
    export: tuple[int, int],
) -> None:
    preset = get_image_preset(key)

    assert preset.background_size == background
    assert preset.composite_size == composite
    assert preset.export_size == export
    assert background[0] * composite[1] == background[1] * composite[0]
    assert composite[0] * export[1] == composite[1] * export[0]


def test_generation_request_defaults_to_legacy_thumbnail_and_shorts_output() -> None:
    request = GenerationRequest(product_id="p", time_slots=["morning"])

    assert request.output_formats == ["thumbnail", "story_vertical"]


@pytest.mark.parametrize(
    "formats",
    [
        [],
        ["thumbnail", "thumbnail"],
        ["thumbnail", "sns_card", "story_vertical"],
        ["detail_banner"],
    ],
)
def test_generation_request_rejects_invalid_output_format_sets(
    formats: list[str],
) -> None:
    with pytest.raises(ValidationError):
        GenerationRequest(
            product_id="p",
            time_slots=["morning"],
            output_formats=formats,
        )


def test_generation_request_accepts_two_distinct_presets_in_request_order() -> None:
    request = GenerationRequest(
        product_id="p",
        time_slots=["morning"],
        output_formats=["sns_card", "story_vertical"],
    )

    assert request.output_formats == ["sns_card", "story_vertical"]
