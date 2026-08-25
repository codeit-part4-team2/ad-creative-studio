from __future__ import annotations

from typing import Literal


FastScenePurpose = Literal["standard", "self_aware", "benefit"]
FAST_SCENE_PURPOSES: tuple[FastScenePurpose, ...] = (
    "standard",
    "self_aware",
    "benefit",
)


_FAST_TONE_SCENES = {
    "emotional": (
        "warm wood wall, natural wood surface, soft light, edge greenery"
    ),
    "modern": (
        "neutral seamless wall, matte floor, gray palette, "
        "rectangular window light"
    ),
    "practical": (
        "bright plain wall, pale counter, even daylight, minimal decor"
    ),
    "premium": (
        "matte charcoal wall, stone surface, thin gold edge light, "
        "restrained atmosphere"
    ),
}

_FAST_TIME_LIGHTING = {
    "morning": "soft morning sunlight",
    "commute_am": "bright angled morning light",
    "afternoon": "balanced daylight",
    "commute_pm": "warm late-afternoon light",
    "evening": "soft warm indoor light",
    "late_night": "low-key warm light, subtle warm edge glow",
}

_BASE_SCENE = (
    "vacant backdrop, bare lower-center surface, plain unmarked wall, "
    "clear center, no text, numbers, signage, or UI, edge accents"
)


_FAST_PURPOSE_SCENES: dict[FastScenePurpose, str] = {
    "standard": "",
    "self_aware": "deadpan dramatic light, stark symmetry, subtly absurd mood",
    "benefit": (
        "welcoming practical light, gentle depth, calm confident mood"
    ),
}


def build_fast_background_prompt(
    *,
    tone: str,
    time_slot: str | None,
    scene_purpose: FastScenePurpose = "standard",
) -> str:
    """Build a fast-path scene prompt without accepting any product semantics."""
    try:
        tone_scene = _FAST_TONE_SCENES[tone]
    except KeyError as exc:
        raise ValueError(f"unsupported fast background tone: {tone}") from exc

    if time_slot is None:
        time_lighting = "balanced light"
    else:
        try:
            time_lighting = _FAST_TIME_LIGHTING[time_slot]
        except KeyError as exc:
            raise ValueError(
                f"unsupported fast background time slot: {time_slot}"
            ) from exc

    try:
        purpose_scene = _FAST_PURPOSE_SCENES[scene_purpose]
    except KeyError as exc:
        raise ValueError(
            f"unsupported fast background scene purpose: {scene_purpose}"
        ) from exc

    return ", ".join(
        part
        for part in (_BASE_SCENE, purpose_scene, tone_scene, time_lighting)
        if part
    )
