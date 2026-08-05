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


def test_estimate_cost_never_raises_on_unregistered_model():
    """MODEL_PRICING에 없는 모델명(오타/신규 모델 등)이어도 KeyError로 죽지 않아야 한다."""
    cost = oc._estimate_cost("totally-unknown-model-xyz", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0  # FALLBACK_PRICING으로 계산됨


def test_call_text_model_returns_response_even_if_cost_tracking_fails(tmp_path, monkeypatch):
    """비용 계산/저장이 실패해도, 이미 받은 API 응답은 호출자에게 정상 반환돼야 한다
    (과금은 됐는데 응답을 못 돌려주는 상황 방지)."""
    _reset_usage_log(tmp_path, monkeypatch)
    monkeypatch.setattr(oc, "_get_client", lambda: _FakeClient(_fake_response(content="정상 응답")))
    monkeypatch.setattr(oc, "_estimate_cost", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    result = oc.call_text_model("테스트")
    assert result == "정상 응답"


def test_call_text_model_falls_back_when_api_call_raises(tmp_path, monkeypatch):
    """레이트리밋/타임아웃 등 API 호출 자체가 예외를 던지면 로컬 폴백으로 전환돼야 한다."""
    _reset_usage_log(tmp_path, monkeypatch)

    class _RaisingClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("simulated rate limit")

    monkeypatch.setattr(oc, "_get_client", lambda: _RaisingClient())

    result = oc.call_text_model("테스트")
    assert "로컬 폴백" in result


def test_record_cost_never_raises_even_on_internal_error(tmp_path, monkeypatch):
    """_record_cost 자체는 내부에서 무슨 일이 있어도 예외를 밖으로 던지지 않는다."""
    _reset_usage_log(tmp_path, monkeypatch)
    monkeypatch.setattr(oc, "_estimate_cost", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    oc._record_cost("gpt-5.6-luna", 100, 100)  # 예외 없이 조용히 지나가야 함
