"""
톤 4종 + 시간대 템플릿.

주의: 회의록 원안은 시간대 3종(아침/점심/저녁)이었으나,
1차 미팅 이후 PM 승인으로 러시아워를 반영한 6종·다중 선택으로 확정됨
(소형가전은 출퇴근 러시아워와 퇴근 후의 구매 심리가 다르다는 근거).
이 템플릿은 승인된 6종 기준입니다.
"""

TONE_TEMPLATES = {
    "emotional": {
        "label": "감성",
        "lighting": "warm natural light",
        "background": "wood tone, cozy props",
        "mood": "relaxed, emotional",
    },
    "modern": {
        "label": "모던",
        "lighting": "neutral studio light",
        "background": "achromatic, minimal studio",
        "mood": "clean, minimal",
    },
    "practical": {
        "label": "실용",
        "lighting": "bright kitchen light",
        "background": "bright kitchen, info badges",
        "mood": "informative, practical",
    },
    "premium": {
        "label": "프리미엄",
        "lighting": "dark background, gold rim light",
        "background": "dark studio, gold highlight",
        "mood": "premium, luxurious",
    },
}

# PM 승인 6종 (기존 3종: morning/afternoon/evening 에서 확장)
# requires_promotion_data=True 인 시간대는, 사용자가 실제 프로모션 정보(할인율/종료시각/쿠폰)를
# 입력했을 때만 "타임딜/카운트다운" 같은 구체적 긴급 문구를 쓴다. 없으면 일반 소구점만 사용한다.
# (재판매 제품 광고 - 허위 할인/이벤트 정보 생성 금지)
TIME_SLOT_TEMPLATES = {
    "morning": {
        "label": "아침",
        "lighting_modifier": "soft morning sunlight",
        "copy_angle": "여유, 준비 — 출근 전 루틴",
        "conversion_goal": "장바구니",
        "requires_promotion_data": False,
    },
    "commute_am": {
        "label": "출근 러시아워",
        "lighting_modifier": "bright quick daylight, dynamic",
        "copy_angle": "즉시결정, 짧은 관여",
        "conversion_goal": "즉시구매",
        "requires_promotion_data": False,
    },
    "afternoon": {
        "label": "오후",
        "lighting_modifier": "neutral bright daylight",
        "copy_angle": "비교, 정보탐색 — 스펙/가격 강조",
        "conversion_goal": "장바구니",
        "requires_promotion_data": False,
    },
    "commute_pm": {
        "label": "퇴근 러시아워",
        "lighting_modifier": "warm late-afternoon light",
        "copy_angle": "즉시결정, 보상심리",
        "conversion_goal": "즉시구매",
        "requires_promotion_data": False,
    },
    "evening": {
        "label": "저녁",
        "lighting_modifier": "warm indoor light, relaxed",
        "copy_angle": "여유, 관계형 — 라이프스타일 연출",
        "conversion_goal": "장바구니",
        "requires_promotion_data": False,
    },
    "late_night": {
        "label": "심야",
        "lighting_modifier": "low warm light, mood lamp",
        "copy_angle": "긴급성 또는 한정성 강조",
        "conversion_goal": "즉시구매",
        "requires_promotion_data": True,  # 프로모션 정보 없으면 "타임딜" 등 구체적 문구 금지
    },
}

COPY_RULES = {
    "headline_max_len": 14,
    "subcopy_max_len": 28,
    "forbidden": [
        "과장 표현 금지",
        "입력에 없는 성능·인증·할인 정보 생성 금지",
    ],
}

OUTPUT_FORMATS = {
    "thumbnail": {"size": (1000, 1000), "label": "썸네일 1:1"},
    "detail_banner": {"size": (860, 400), "label": "상세페이지 배너"},
    "sns_card": {"size": (1080, 1350), "label": "SNS 카드 4:5"},
}

MAX_TIME_SLOTS_PER_REQUEST = 3  # GPU 대기열 보호용 상한 (실측 후 조정)
SECONDS_PER_GENERATION = 15  # 톤 1개 기준 가정치 - R3 실측으로 교체 예정


def estimate_seconds(num_tones: int, num_time_slots: int) -> int:
    return num_tones * num_time_slots * SECONDS_PER_GENERATION
