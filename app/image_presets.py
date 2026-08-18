from __future__ import annotations

from dataclasses import dataclass, replace
from math import gcd
from types import MappingProxyType
from typing import Final, Literal, Mapping, cast


OutputFormatLiteral = Literal[
    "thumbnail",
    "sns_card",
    "story_vertical",
    "wide_banner",
]


@dataclass(frozen=True, slots=True)
class ImagePreset:
    key: OutputFormatLiteral
    label: str
    background_size: tuple[int, int]
    composite_size: tuple[int, int]
    export_size: tuple[int, int]
    filename_suffix: str


IMAGE_PRESETS: Final[Mapping[OutputFormatLiteral, ImagePreset]] = MappingProxyType(
    {
        "thumbnail": ImagePreset(
            key="thumbnail",
            label="정사각형 1:1",
            background_size=(768, 768),
            composite_size=(1024, 1024),
            export_size=(1080, 1080),
            filename_suffix="1x1",
        ),
        "sns_card": ImagePreset(
            key="sns_card",
            label="SNS 피드 4:5",
            background_size=(672, 840),
            composite_size=(896, 1120),
            export_size=(1080, 1350),
            filename_suffix="4x5",
        ),
        "story_vertical": ImagePreset(
            key="story_vertical",
            label="쇼츠·스토리 9:16",
            background_size=(576, 1024),
            composite_size=(720, 1280),
            export_size=(1080, 1920),
            filename_suffix="9x16",
        ),
        "wide_banner": ImagePreset(
            key="wide_banner",
            label="웹 배너 16:9",
            background_size=(1024, 576),
            composite_size=(1280, 720),
            export_size=(1280, 720),
            filename_suffix="16x9",
        ),
    }
)

DEFAULT_BACKGROUND_REFERENCE: Final = 768
DEFAULT_COMPOSITE_REFERENCE: Final = 1024


def _scale_ratio_size(
    size: tuple[int, int],
    *,
    configured_reference: int,
    default_reference: int,
) -> tuple[int, int]:
    """Scale a preset on an 8-pixel grid without changing its exact ratio."""
    if configured_reference <= 0:
        raise ValueError("configured reference size must be positive")
    if configured_reference == default_reference:
        return size

    unit = gcd(*size)
    ratio_width, ratio_height = size[0] // unit, size[1] // unit
    aligned_steps = (
        unit * configured_reference + default_reference * 4
    ) // (default_reference * 8)
    scaled_unit = max(8, aligned_steps * 8)
    return ratio_width * scaled_unit, ratio_height * scaled_unit


def get_image_preset(key: str) -> ImagePreset:
    try:
        return IMAGE_PRESETS[cast(OutputFormatLiteral, key)]
    except KeyError as exc:
        raise ValueError(f"unsupported output format: {key}") from exc


def resolve_runtime_image_preset(
    key: str,
    *,
    fast_background_size: int,
    image_size: int,
) -> ImagePreset:
    """Apply runtime tuning sizes while preserving each preset's native ratio."""
    preset = get_image_preset(key)
    return replace(
        preset,
        background_size=_scale_ratio_size(
            preset.background_size,
            configured_reference=fast_background_size,
            default_reference=DEFAULT_BACKGROUND_REFERENCE,
        ),
        composite_size=_scale_ratio_size(
            preset.composite_size,
            configured_reference=image_size,
            default_reference=DEFAULT_COMPOSITE_REFERENCE,
        ),
    )
