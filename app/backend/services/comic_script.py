from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


SCRIPT_VERSION = "deadpan-ai-v1"
_HANGUL_TEXT = re.compile(r"^[가-힣\s.,!?]+$")


class ComicLineKind(str, Enum):
    INTRO = "intro"
    SELF_AWARE = "self_aware"
    BENEFIT = "benefit"
    CTA = "cta"


@dataclass(frozen=True, slots=True)
class PronunciationResult:
    display_text: str
    spoken_text: str
    review_required: bool


class PronunciationLexicon:
    def __init__(self, entries: Mapping[str, str]) -> None:
        self._entries = {
            str(display).strip(): str(spoken).strip()
            for display, spoken in entries.items()
            if str(display).strip() and str(spoken).strip()
        }

    def resolve(self, text: str) -> PronunciationResult:
        display_text = str(text).strip()
        if not display_text:
            raise ValueError("발음 확인 대상은 비어 있을 수 없습니다")
        if display_text in self._entries:
            return PronunciationResult(
                display_text=display_text,
                spoken_text=self._entries[display_text],
                review_required=False,
            )
        return PronunciationResult(
            display_text=display_text,
            spoken_text=display_text,
            review_required=_HANGUL_TEXT.fullmatch(display_text) is None,
        )


@dataclass(frozen=True, slots=True)
class ComicLine:
    display_text: str
    spoken_text: str
    kind: ComicLineKind
    pronunciation_review_required: bool = False


@dataclass(frozen=True, slots=True)
class ComicScript:
    lines: tuple[ComicLine, ...]
    version: str = SCRIPT_VERSION

    @property
    def pronunciation_review_required(self) -> bool:
        return any(line.pronunciation_review_required for line in self.lines)


def _line(
    *,
    display_text: str,
    spoken_text: str,
    kind: ComicLineKind,
    review_required: bool = False,
) -> ComicLine:
    return ComicLine(
        display_text=display_text,
        spoken_text=spoken_text,
        kind=kind,
        pronunciation_review_required=review_required,
    )


def build_comic_script(
    *,
    product_name: str,
    selling_points: tuple[str, ...],
    time_slot: str,
    lexicon: PronunciationLexicon,
) -> ComicScript:
    if time_slot not in {"commute_am", "commute_pm"}:
        raise ValueError("코믹 쇼츠는 출근·퇴근 시간대만 지원합니다")

    product = lexicon.resolve(product_name)
    intro = _line(
        display_text=f"{product.display_text}입니다.",
        spoken_text=f"{product.spoken_text}입니다.",
        kind=ComicLineKind.INTRO,
        review_required=product.review_required,
    )

    self_aware_text = (
        "저는 시간을 느끼지 못합니다."
        if time_slot == "commute_am"
        else "저는 퇴근을 하지 않습니다."
    )
    self_aware = _line(
        display_text=self_aware_text,
        spoken_text=self_aware_text,
        kind=ComicLineKind.SELF_AWARE,
    )

    if selling_points:
        selling_point = lexicon.resolve(selling_points[0])
        benefit = _line(
            display_text=f"주요 특징은 {selling_point.display_text}입니다.",
            spoken_text=f"주요 특징은 {selling_point.spoken_text}입니다.",
            kind=ComicLineKind.BENEFIT,
            review_required=selling_point.review_required,
        )
    else:
        benefit = _line(
            display_text="제품의 주요 특징을 확인해 보세요.",
            spoken_text="제품의 주요 특징을 확인해 보세요.",
            kind=ComicLineKind.BENEFIT,
        )

    time_phrase = "출근 전에" if time_slot == "commute_am" else "퇴근길에"
    cta = _line(
        display_text=(
            f"{product.display_text}. {time_phrase} 확인해 보세요."
        ),
        spoken_text=(
            f"{product.spoken_text}. {time_phrase} 확인해 보세요."
        ),
        kind=ComicLineKind.CTA,
        review_required=product.review_required,
    )
    return ComicScript(lines=(intro, self_aware, benefit, cta))
