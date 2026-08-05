import json

from app.backend.services import copy_generator
from app.prompt.schemas import PromptRequest


def _req(**overrides):
    defaults = dict(product_name="스팀 에어프라이어 5L", tone="emotional", time_slot="morning")
    defaults.update(overrides)
    return PromptRequest(**defaults)


def test_build_ad_copy_uses_rule_based_when_llm_disabled(monkeypatch):
    monkeypatch.setattr(copy_generator, "USE_LLM_COPY", False)
    headline, subcopy = copy_generator.build_ad_copy(_req())
    assert headline
    assert subcopy


def test_build_ad_copy_uses_llm_when_enabled_and_valid_json(monkeypatch):
    monkeypatch.setattr(copy_generator, "USE_LLM_COPY", True)
    monkeypatch.setattr(
        copy_generator.openai_client, "call_text_model",
        lambda *a, **k: json.dumps({"headline": "LLM 헤드라인", "subcopy": "LLM 서브카피"}),
    )
    headline, subcopy = copy_generator.build_ad_copy(_req())
    assert headline == "LLM 헤드라인"
    assert subcopy == "LLM 서브카피"


def test_build_ad_copy_falls_back_to_rule_based_on_invalid_json(monkeypatch):
    monkeypatch.setattr(copy_generator, "USE_LLM_COPY", True)
    monkeypatch.setattr(copy_generator.openai_client, "call_text_model", lambda *a, **k: "이건 JSON이 아님")

    headline, subcopy = copy_generator.build_ad_copy(_req())
    # 규칙 기반 결과와 동일해야 함 (폴백 성공)
    expected_headline, expected_subcopy = copy_generator.prompt_builder.build_ad_copy(_req())
    assert headline == expected_headline
    assert subcopy == expected_subcopy


def test_build_ad_copy_falls_back_when_llm_raises(monkeypatch):
    monkeypatch.setattr(copy_generator, "USE_LLM_COPY", True)

    def _raise(*a, **k):
        raise RuntimeError("API 오류")

    monkeypatch.setattr(copy_generator.openai_client, "call_text_model", _raise)
    headline, subcopy = copy_generator.build_ad_copy(_req())
    assert headline  # 폴백으로 뭔가는 나와야 함
    assert subcopy


def test_build_ad_copy_truncates_overlong_llm_response(monkeypatch):
    monkeypatch.setattr(copy_generator, "USE_LLM_COPY", True)
    long_headline = "가" * 50
    monkeypatch.setattr(
        copy_generator.openai_client, "call_text_model",
        lambda *a, **k: json.dumps({"headline": long_headline, "subcopy": "짧음"}),
    )
    headline, _ = copy_generator.build_ad_copy(_req())
    assert len(headline) <= copy_generator.COPY_RULES["headline_max_len"]


def test_llm_path_is_skipped_entirely_for_promotion_required_slot_without_promotion(monkeypatch):
    """
    허위 정보 가드레일: requires_promotion_data인 시간대(예: 심야)인데 실제 프로모션 정보가
    없으면, LLM한테 "지어내지 마세요"라고 프롬프트로 부탁하는 것만으로는 검증이 안 되므로
    LLM 자체를 호출하지 않고 규칙 기반(builder)으로 가야 한다.
    """
    monkeypatch.setattr(copy_generator, "USE_LLM_COPY", True)

    called = {"count": 0}

    def _should_not_be_called(*a, **k):
        called["count"] += 1
        return '{"headline": "오늘 밤 12시까지 15% 할인", "subcopy": "지금이 기회"}'

    monkeypatch.setattr(copy_generator.openai_client, "call_text_model", _should_not_be_called)

    req = _req(tone="premium", time_slot="late_night")  # requires_promotion_data=True, promotion 없음
    headline, subcopy = copy_generator.build_ad_copy(req)

    assert called["count"] == 0  # LLM이 아예 호출되면 안 됨
    assert "타임딜" not in headline + subcopy
    assert "12시" not in headline + subcopy


def test_llm_path_is_used_when_promotion_data_is_provided(monkeypatch):
    """프로모션 정보가 실제로 있으면 LLM 경로를 정상적으로 탄다."""
    from app.prompt.schemas import PromotionInfo

    monkeypatch.setattr(copy_generator, "USE_LLM_COPY", True)
    monkeypatch.setattr(
        copy_generator.openai_client, "call_text_model",
        lambda *a, **k: '{"headline": "15% 할인", "subcopy": "오늘 밤까지"}',
    )

    req = _req(tone="premium", time_slot="late_night",
                promotion=PromotionInfo(discount_percent=15, ends_at="24:00"))
    headline, subcopy = copy_generator.build_ad_copy(req)
    assert headline == "15% 할인"
