import pytest

from app.prompt.backgrounds import FAST_SCENE_PURPOSES, build_fast_background_prompt
from app.prompt.templates import TIME_SLOT_TEMPLATES, TONE_TEMPLATES
from model_server.pipelines import build_background_prompt


@pytest.mark.parametrize("tone", list(TONE_TEMPLATES))
@pytest.mark.parametrize("time_slot", list(TIME_SLOT_TEMPLATES))
@pytest.mark.parametrize("scene_purpose", FAST_SCENE_PURPOSES)
def test_fast_background_prompt_stays_product_agnostic_for_every_scene(
    tone: str,
    time_slot: str,
    scene_purpose: str,
) -> None:
    prompt = build_fast_background_prompt(
        tone=tone,
        time_slot=time_slot,
        scene_purpose=scene_purpose,
    )
    normalized = prompt.casefold()

    assert "vacant backdrop" in normalized
    assert "bare lower-center surface" in normalized
    assert "plain unmarked wall" in normalized
    # The 310-character guard keeps every typed scene variant below CLIP's
    # 77-token conditioning limit with measured headroom.
    assert len(build_background_prompt(prompt)) <= 310
    assert all(
        risky_term not in normalized
        for risky_term in (
            "product",
            "appliance",
            "device",
            "package",
            "preserved",
            "selling point",
            "fan",
            "air conditioner",
            "clock",
            "watch",
            "logo",
            "badge",
            "poster",
            "signboard",
            "typography",
            "advertising",
            "commercial",
            "studio",
            "luxury",
        )
    )


def test_standard_fast_background_prompt_uses_tone_and_time_context() -> None:
    prompt = build_fast_background_prompt(tone="premium", time_slot="late_night")

    assert "matte charcoal wall" in prompt
    assert "subtle warm edge glow" in prompt
    assert "mood lamp" not in prompt


def test_modern_background_avoids_clock_like_light_geometry() -> None:
    prompt = build_fast_background_prompt(tone="modern", time_slot="afternoon")

    assert "rectangular window light" in prompt
    assert "geometric light" not in prompt


def test_shorts_scene_purposes_are_explicit_and_distinct() -> None:
    prompts = {
        purpose: build_fast_background_prompt(
            tone="premium",
            time_slot="commute_pm",
            scene_purpose=purpose,
        )
        for purpose in FAST_SCENE_PURPOSES
    }

    assert len(set(prompts.values())) == len(FAST_SCENE_PURPOSES)
    assert "deadpan dramatic light" in prompts["self_aware"]
    assert "welcoming practical light" in prompts["benefit"]
