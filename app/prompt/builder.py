"""
Builder 역할:
사용자 입력 -> 톤 템플릿 결합 -> 시간대 템플릿 결합 -> 제품 보존 지시 추가
-> 이미지 프롬프트 생성(영어) -> 한국어 광고 문구 생성

톤 문구 템플릿 자체(카피 톤앤매너)는 유수빈님이 정의해서 넘겨줄 예정 -
여기서는 그 템플릿을 꽂을 구조/인터페이스만 먼저 만든다.

재판매 제품 광고이므로: 사용자가 입력하지 않은 성능·인증·할인·이벤트 정보를
문구에 만들어 넣지 않는다 (COPY_RULES, requires_promotion_data 참고).
"""
from .schemas import PromptRequest, PromptResult
from .templates import TONE_TEMPLATES, TIME_SLOT_TEMPLATES, COPY_RULES

PRODUCT_PRESERVATION_INSTRUCTION = (
    "Product must be preserved exactly as uploaded "
    "(do not alter product shape, color, or logo)."
)

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, distorted product, extra logo, watermark, fake text, "
    "wristwatch, watch face, clock, timer, dial, secondary product, "
    "duplicate appliance, large circular prop, dominant background object, "
    "softbox, tripod, studio light, photography equipment"
)


def build_image_prompt(req: PromptRequest) -> str:
    tone = TONE_TEMPLATES[req.tone]
    parts = [
        f"Create a product advertisement background for {req.product_name}.",
        f"Tone: {tone['label']} - {tone['lighting']}, {tone['background']}, {tone['mood']}.",
    ]
    if req.time_slot:
        slot = TIME_SLOT_TEMPLATES[req.time_slot]
        parts.append(f"Time: {slot['label']} - {slot['lighting_modifier']}.")
    if req.selling_points:
        parts.append("Key selling points: " + ", ".join(req.selling_points) + ".")
    parts.append(PRODUCT_PRESERVATION_INSTRUCTION)
    return " ".join(parts)


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def build_ad_copy(req: PromptRequest) -> tuple[str, str]:
    """
    한국어 헤드라인/서브카피 생성.
    TODO: 실제로는 app/backend/services/openai_client.py 의 공용 래퍼로 교체.
    지금은 R2/R3 및 UI 통합 테스트를 위한 더미 응답 - 톤 문구 템플릿은 유수빈님 전달분으로 교체 예정.

    규칙(COPY_RULES):
    - 헤드라인 14자 / 서브카피 28자 이내
    - 과장 표현 금지, 입력에 없는 성능·인증·할인 정보 생성 금지
    - requires_promotion_data=True인 시간대(예: 심야)는 req.promotion이 없으면
      "타임딜/카운트다운" 같은 구체적 긴급 문구를 쓰지 않는다
    """
    tone_label = TONE_TEMPLATES[req.tone]["label"]
    slot = TIME_SLOT_TEMPLATES[req.time_slot] if req.time_slot else None

    if slot and slot["requires_promotion_data"] and not req.promotion:
        # 프로모션 정보 없음 -> 일반적인 문구로 대체 (허위 긴급성 생성 금지)
        headline = _truncate(f"{req.product_name} 편안한 선택", COPY_RULES["headline_max_len"])
        subcopy = _truncate("하루 끝, 나를 위한 편리한 선택", COPY_RULES["subcopy_max_len"])
    elif slot and slot["requires_promotion_data"] and req.promotion:
        promo = req.promotion
        promo_text = ""
        if promo.discount_percent:
            promo_text += f"{promo.discount_percent}% 할인"
        if promo.ends_at:
            promo_text += f" · {promo.ends_at}까지" if promo_text else f"{promo.ends_at}까지"
        headline = _truncate(promo_text or f"{tone_label} 한정 혜택", COPY_RULES["headline_max_len"])
        subcopy = _truncate(f"{req.product_name} 지금 확인하세요", COPY_RULES["subcopy_max_len"])
    else:
        angle = slot["copy_angle"] if slot else "기본"
        headline = _truncate(f"[{tone_label}] {req.product_name}", COPY_RULES["headline_max_len"])
        subcopy = _truncate(angle, COPY_RULES["subcopy_max_len"])

    return headline, subcopy


def build(req: PromptRequest) -> PromptResult:
    headline, subcopy = build_ad_copy(req)
    return PromptResult(
        image_prompt=build_image_prompt(req),
        headline=headline,
        subcopy=subcopy,
        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
    )
