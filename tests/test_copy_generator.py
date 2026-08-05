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
