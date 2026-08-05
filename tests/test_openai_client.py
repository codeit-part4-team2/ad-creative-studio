from types import SimpleNamespace

from app.backend.services import openai_client as oc


def _fake_response(prompt_tokens=1000, completion_tokens=500, content="더미 응답"):
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


class _FakeChatCompletions:
    def __init__(self, response):
        self._response = response

    def create(self, **kwargs):
        return self._response


class _FakeChat:
    def __init__(self, response):
        self.completions = _FakeChatCompletions(response)


class _FakeClient:
    def __init__(self, response):
        self.chat = _FakeChat(response)


def _reset_usage_log(tmp_path, monkeypatch):
    fake_log = tmp_path / "openai_usage.json"
    monkeypatch.setattr(oc, "USAGE_LOG_PATH", fake_log)


def test_estimate_cost_uses_model_pricing():
    cost = oc._estimate_cost("gpt-5.6-luna", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == 1.00 + 6.00  # luna: $1/$6 per 1M


def test_estimate_cost_unknown_model_falls_back_to_default():
    cost = oc._estimate_cost("unknown-model", prompt_tokens=1_000_000, completion_tokens=0)
    input_rate, _ = oc.MODEL_PRICING[oc.DEFAULT_MODEL]
    assert cost == input_rate


def test_call_text_model_tracks_cumulative_spend(tmp_path, monkeypatch):
    _reset_usage_log(tmp_path, monkeypatch)
    monkeypatch.setattr(oc, "_get_client", lambda: _FakeClient(_fake_response()))

    oc.call_text_model("테스트 프롬프트", model="gpt-5.6-luna")
    usage_after_1 = oc.get_usage()
    assert usage_after_1["spent_usd"] > 0

    oc.call_text_model("두번째 프롬프트", model="gpt-5.6-luna")
    usage_after_2 = oc.get_usage()
    assert usage_after_2["spent_usd"] > usage_after_1["spent_usd"]  # 누적되어야 함


def test_call_text_model_falls_back_when_over_budget(tmp_path, monkeypatch):
    _reset_usage_log(tmp_path, monkeypatch)
    oc._save_spent(oc.HARD_LIMIT_USD + 1)  # 예산 초과 상태로 미리 세팅

    result = oc.call_text_model("아무 프롬프트")
    assert "로컬 폴백" in result


def test_get_usage_flags_over_warning(tmp_path, monkeypatch):
    _reset_usage_log(tmp_path, monkeypatch)
    oc._save_spent(oc.WARNING_USD + 0.01)

    usage = oc.get_usage()
    assert usage["over_warning"] is True
    assert usage["over_limit"] is False
