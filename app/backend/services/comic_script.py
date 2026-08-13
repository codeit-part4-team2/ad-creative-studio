from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


SCRIPT_VERSION = "deadpan-ai-v2"
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


@dataclass(frozen=True, slots=True)
class _ScriptTemplate:
    intro: str
    self_aware: str
    cta: str


_TEMPLATES = {
    "commute_am": (
        _ScriptTemplate(
            intro="{product}, 출근길에 짧게 소개할게요.",
            self_aware="광고라서 칭찬은 해야 합니다. 과장은 안 하겠습니다.",
            cta="필요하셨다면 확인해 보세요. 저는 계속 여기 있겠습니다.",
        ),
        _ScriptTemplate(
            intro="바쁜 아침이니 {product}부터 보여드릴게요.",
            self_aware="저는 잠이 없어서 아침 광고도 괜찮습니다.",
            cta="출근 전에 한 번 확인해 보세요. 저는 지각하지 않습니다.",
        ),
    ),
    "commute_pm": (
        _ScriptTemplate(
            intro="{product}, 퇴근길에 짧게 소개할게요.",
            self_aware="저는 퇴근이 없습니다. 광고는 계속할 수 있습니다.",
            cta="필요하셨다면 확인해 보세요. 저는 먼저 퇴근하지 않겠습니다.",
        ),
        _ScriptTemplate(
            intro="퇴근 중이시라면 {product}만 보고 가세요.",
            self_aware="광고라서 활기차야 합니다. 목소리는 이게 최선입니다.",
            cta="퇴근길에 한 번 확인해 보세요. 저는 계속 여기 있겠습니다.",
        ),
    ),
}


def _select_template(*, product_name: str, time_slot: str) -> _ScriptTemplate:
    templates = _TEMPLATES[time_slot]
    stable_key = f"{product_name.strip().casefold()}\0{time_slot}".encode("utf-8")
    index = hashlib.sha256(stable_key).digest()[1] % len(templates)
    return templates[index]


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
    template = _select_template(
        product_name=product.display_text,
        time_slot=time_slot,
    )
    intro = _line(
        display_text=template.intro.format(product=product.display_text),
        spoken_text=template.intro.format(product=product.spoken_text),
        kind=ComicLineKind.INTRO,
        review_required=product.review_required,
    )

    self_aware = _line(
        display_text=template.self_aware,
        spoken_text=template.self_aware,
        kind=ComicLineKind.SELF_AWARE,
    )

    if selling_points:
        selling_point = lexicon.resolve(selling_points[0])
        benefit = _line(
            display_text=(
                f"주요 특징을 말씀드리면, {selling_point.display_text}입니다."
            ),
            spoken_text=(
                f"주요 특징을 말씀드리면, {selling_point.spoken_text}입니다."
            ),
            kind=ComicLineKind.BENEFIT,
            review_required=selling_point.review_required,
        )
    else:
        benefit = _line(
            display_text="제품의 주요 특징을 확인해 보세요.",
            spoken_text="제품의 주요 특징을 확인해 보세요.",
            kind=ComicLineKind.BENEFIT,
        )

    cta = _line(
        display_text=template.cta,
        spoken_text=template.cta,
        kind=ComicLineKind.CTA,
    )
    return ComicScript(lines=(intro, self_aware, benefit, cta))
