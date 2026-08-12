import pytest

from app.prompt.builder import build
from app.prompt.schemas import PromptRequest, PromotionInfo
from app.prompt.templates import TIME_SLOT_TEMPLATES, TONE_TEMPLATES


def test_build_includes_product_preservation_instruction():
    req = PromptRequest(
        product_name="스팀 에어프라이어 5L",
        tone="emotional",
        time_slot="commute_pm",
    )
    result = build(req)
    assert "preserved exactly as uploaded" in result.image_prompt
    assert result.headline
    assert result.subcopy


def test_build_without_time_slot_still_works():
    req = PromptRequest(product_name="무선 청소기", tone="modern")
    result = build(req)
    assert "무선 청소기" in result.image_prompt


@pytest.mark.parametrize("time_slot", list(TIME_SLOT_TEMPLATES.keys()))
@pytest.mark.parametrize("tone", list(TONE_TEMPLATES.keys()))
def test_all_tone_time_slot_combinations_build_successfully(tone, time_slot):
    """시간대 6종 x 톤 4종 = 24개 조합이 전부 정상 동작하는지."""
    req = PromptRequest(product_name="공기청정기", tone=tone, time_slot=time_slot)
    result = build(req)
    assert result.image_prompt
    assert result.headline
    assert result.subcopy
    assert "preserved exactly as uploaded" in result.image_prompt


def test_late_night_without_promotion_avoids_fake_urgency_copy():
    """심야(requires_promotion_data=True)인데 프로모션 정보가 없으면 '타임딜' 등을 지어내지 않는다."""
    req = PromptRequest(product_name="전기포트", tone="premium", time_slot="late_night")
    result = build(req)
    assert "타임딜" not in result.headline + result.subcopy
    assert "카운트다운" not in result.headline + result.subcopy


def test_late_night_with_promotion_uses_actual_promotion_data():
    req = PromptRequest(
        product_name="전기포트",
        tone="premium",
        time_slot="late_night",
        promotion=PromotionInfo(discount_percent=15, ends_at="24:00"),
    )
    result = build(req)
    assert "15%" in result.headline


def test_headline_and_subcopy_respect_length_limits():
    req = PromptRequest(
        product_name="아주아주아주아주아주긴제품명입니다정말로",
        tone="modern",
        time_slot="afternoon",
    )
    result = build(req)
    assert len(result.headline) <= 14
    assert len(result.subcopy) <= 28


def test_premium_prompt_uses_a_restrained_set_without_watch_like_hero_props():
    result = build(PromptRequest(product_name="air purifier", tone="premium"))

    assert "matte charcoal wall" in result.image_prompt
    assert "stone plinth" in result.image_prompt
    assert "thin linear gold light" in result.image_prompt
    assert "restrained premium studio" in result.image_prompt
    assert "luxurious" not in result.image_prompt


def test_negative_prompt_rejects_competing_objects_and_photography_equipment():
    result = build(PromptRequest(product_name="air purifier", tone="premium"))

    rejected_objects = (
        "wristwatch",
        "watch face",
        "clock",
        "timer",
        "dial",
        "secondary product",
        "duplicate appliance",
        "large circular prop",
        "softbox",
        "tripod",
        "studio light",
        "photography equipment",
    )
    assert all(item in result.negative_prompt for item in rejected_objects)
