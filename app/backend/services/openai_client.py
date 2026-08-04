"""
OpenAI 공용 래퍼 (텍스트 전용 - 결정 8). 모든 OpenAI 호출은 이 함수 하나만 통과한다.
$20 경고 / $25 도달 시 이후 호출은 로컬 텍스트 모델로 강제 전환.
"""
import os
import json
import time
from pathlib import Path

WARNING_USD = float(os.getenv("OPENAI_WARNING_THRESHOLD_USD", 20))
HARD_LIMIT_USD = float(os.getenv("OPENAI_BUDGET_LIMIT_USD", 25))
# 소스 디렉토리가 아니라 logs/ 에 저장 - .gitignore가 logs/ 를 이미 제외하므로 실수 커밋 방지
USAGE_LOG_PATH = Path("logs/openai_usage.json")
USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


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


def call_text_model(prompt: str, model: str | None = None) -> str:
    spent = _load_spent()
    if spent >= HARD_LIMIT_USD:
        return _call_local_fallback(prompt)
    if spent >= WARNING_USD:
        print(f"[WARNING] OpenAI 누적 비용 ${spent:.2f} — 경고선(${WARNING_USD}) 초과")

    model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    # TODO: 실제 openai SDK 호출 + 응답 토큰 기반 비용 계산 후 _save_spent 갱신
    return f"[더미 응답 - {model}] {prompt[:50]}..."


def _call_local_fallback(prompt: str) -> str:
    # TODO: 예산 초과 시 로컬 소형 텍스트 모델로 대체
    return f"[로컬 폴백 응답] {prompt[:50]}..."
