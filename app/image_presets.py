from __future__ import annotations

from dataclasses import dataclass
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


def get_image_preset(key: str) -> ImagePreset:
    try:
        return IMAGE_PRESETS[cast(OutputFormatLiteral, key)]
    except KeyError as exc:
        raise ValueError(f"unsupported output format: {key}") from exc
