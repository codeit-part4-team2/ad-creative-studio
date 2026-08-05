"""
M3(광고 문구 자동 생성) 실제 연동.

기본은 app/prompt/builder.py의 규칙 기반 문구(결정적, 테스트 용이)를 그대로 쓴다.
USE_LLM_COPY=true 환경변수가 켜져 있으면 OpenAI로 더 자연스러운 문구 생성을 시도하고,
실패하면(파싱 오류·API 오류·예산초과 등 무엇이든) 규칙 기반으로 조용히 폴백한다.
즉 LLM 문구 생성은 "있으면 더 좋은" 보강이지, 실패해도 서비스가 멈추지 않는다.
"""
import json
import os

from app.prompt.schemas import PromptRequest
from app.prompt import builder as prompt_builder
from app.prompt.templates import COPY_RULES, TONE_TEMPLATES, TIME_SLOT_TEMPLATES
from app.backend.services import openai_client

USE_LLM_COPY = os.getenv("USE_LLM_COPY", "false").lower() == "true"
# 주의: 이 값은 모듈 import 시 1회만 읽힌다 - 서버 실행 중 .env를 바꿔도
# 재시작 전까지는 반영 안 됨 (일반적인 설정 로딩 방식이라 문제는 아니지만,
# UI에서 실시간 토글이 필요해지면 함수 호출 시점에 os.getenv를 다시 읽도록 분리할 것)

SYSTEM_PROMPT = (
    "당신은 소형가전 광고 카피라이터입니다. 반드시 JSON으로만 답하세요: "
    '{"headline": "...", "subcopy": "..."}. '
    f"headline은 {COPY_RULES['headline_max_len']}자 이내, subcopy는 {COPY_RULES['subcopy_max_len']}자 이내로 "
    "간결하게 작성하세요. 과장 표현 금지. 입력에 없는 성능·인증·할인 정보를 지어내지 마세요."
)


def build_ad_copy(req: PromptRequest) -> tuple[str, str]:
    if not USE_LLM_COPY:
        return prompt_builder.build_ad_copy(req)

    try:
        tone_label = TONE_TEMPLATES[req.tone]["label"]
        slot_label = TIME_SLOT_TEMPLATES[req.time_slot]["label"] if req.time_slot else "기본"
        user_prompt = (
            f"제품명: {req.product_name}\n"
            f"톤: {tone_label}\n"
            f"시간대: {slot_label}\n"
            f"셀링포인트: {', '.join(req.selling_points) if req.selling_points else '없음'}"
        )
        raw = openai_client.call_text_model(user_prompt, system=SYSTEM_PROMPT)
        data = json.loads(raw)
        headline = str(data["headline"]).strip()[: COPY_RULES["headline_max_len"]]
        subcopy = str(data["subcopy"]).strip()[: COPY_RULES["subcopy_max_len"]]
        if not headline or not subcopy:
            raise ValueError("빈 응답")
        return headline, subcopy
    except Exception as exc:  # noqa: BLE001 - 문구 생성 실패가 전체 생성 흐름을 막으면 안 됨
        print(f"[WARNING] LLM 문구 생성 실패, 규칙 기반으로 폴백: {exc}")
        return prompt_builder.build_ad_copy(req)
