"""
OpenAI 공용 래퍼 (텍스트 전용 - 결정 8). 모든 OpenAI 호출은 이 함수 하나만 통과한다.
$20 도달 시 경고 로그, $25 도달 시 이후 호출은 로컬 텍스트 모델로 강제 전환.

모델 단가는 2026-08 기준 (Prompt Spec / 팀 조사 결과) - 가격은 변동 가능하니
실제 사용 시 https://platform.openai.com/docs/pricing 로 한 번 더 확인 권장.
단가는 1M 토큰당 USD.
"""
import os
import json
import time
from pathlib import Path
from typing import Optional

WARNING_USD = float(os.getenv("OPENAI_WARNING_THRESHOLD_USD", 20))
HARD_LIMIT_USD = float(os.getenv("OPENAI_BUDGET_LIMIT_USD", 25))
# 소스 디렉토리가 아니라 logs/ 에 저장 - .gitignore가 logs/ 를 이미 제외하므로 실수 커밋 방지
USAGE_LOG_PATH = Path("logs/openai_usage.json")
USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

# 1M 토큰당 USD (input, output) - 실제 요금은 위 문서로 재확인
MODEL_PRICING = {
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.6-sol": (5.00, 30.00),
}

_client = None  # openai.OpenAI 인스턴스, 최초 호출 시 lazy init


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI  # 여기서 import - key 없이 모듈 로드만 할 때 에러 안 나게

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY가 설정되지 않았습니다. .env에 키를 넣어주세요 (.env.example 참고)."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def _load_spent() -> float:
    if USAGE_LOG_PATH.exists():
        return json.loads(USAGE_LOG_PATH.read_text()).get("spent_usd", 0.0)
    return 0.0


def _save_spent(spent_usd: float) -> None:
    USAGE_LOG_PATH.write_text(json.dumps({"spent_usd": spent_usd, "updated_at": time.time()}))


def get_usage() -> dict:
    spent = _load_spent()
    return {
        "spent_usd": round(spent, 4),
        "warning_threshold": WARNING_USD,
        "hard_limit": HARD_LIMIT_USD,
        "over_warning": spent >= WARNING_USD,
        "over_limit": spent >= HARD_LIMIT_USD,
    }


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_rate, output_rate = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    return (prompt_tokens / 1_000_000) * input_rate + (completion_tokens / 1_000_000) * output_rate


def call_text_model(prompt: str, model: Optional[str] = None, system: Optional[str] = None) -> str:
    """
    공용 래퍼 - 텍스트 생성은 이 함수만 호출한다 (개인 실험용 직접 SDK 호출 금지, 결정 8).
    $25 예산 초과 시 자동으로 로컬 폴백으로 전환된다.
    """
    spent = _load_spent()
    if spent >= HARD_LIMIT_USD:
        print(f"[BUDGET] 예산 상한(${HARD_LIMIT_USD}) 초과 — 로컬 폴백으로 전환")
        return _call_local_fallback(prompt)
    if spent >= WARNING_USD:
        print(f"[WARNING] OpenAI 누적 비용 ${spent:.2f} — 경고선(${WARNING_USD}) 초과")

    model = model or DEFAULT_MODEL
    client = _get_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(model=model, messages=messages)

    usage = response.usage
    cost = _estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)
    _save_spent(spent + cost)

    return response.choices[0].message.content


def _call_local_fallback(prompt: str) -> str:
    # TODO: 예산 초과 시 로컬 소형 텍스트 모델로 대체 (결정 8) - 지금은 더미 응답
    return f"[로컬 폴백 응답 - 예산 초과] {prompt[:50]}..."
