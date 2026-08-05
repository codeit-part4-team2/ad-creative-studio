"""
시간대별 제품 노출 알고리즘 (강사님 피드백 반영, S1 대응).

핵심 로직:
1. 현재 시각 -> 어느 시간대 슬롯에 해당하는지 판정 (get_current_time_slot)
2. 해당 상품의 생성 이력(History)에서, 그 슬롯으로 생성된 결과가 있는지 조회 (pick_exposure)
3. 있으면 "지금 노출해야 할 배너"로 반환, 없으면 미생성 안내
"""
from datetime import datetime
from typing import Optional

from app.prompt.templates import TIME_SLOT_TEMPLATES


def get_current_time_slot(now: Optional[datetime] = None) -> str:
    """현재 시각(now 생략 시 실제 현재 시각)이 어느 시간대 슬롯에 해당하는지 반환."""
    now = now or datetime.now()
    hour_float = now.hour + now.minute / 60

    for slot, info in TIME_SLOT_TEMPLATES.items():
        start, end = info["hour_range"]
        if start < end:
            if start <= hour_float < end:
                return slot
        else:
            # 자정을 넘어가는 구간 (예: 22:00 ~ 05:59)
            if hour_float >= start or hour_float < end:
                return slot

    raise RuntimeError("시간대 판정 실패 - TIME_SLOT_TEMPLATES의 hour_range를 확인하세요")


def pick_exposure(product_id: str, history: list[dict], now: Optional[datetime] = None) -> dict:
    """
    현재 시간대에 노출해야 할 결과를 History에서 찾는다.

    Returns:
        {
            "time_slot": "commute_am",
            "time_slot_label": "출근 러시아워",
            "available": True/False,
            "tones": [...] | None,   # 해당 시간대의 톤 4종 결과 (available=True일 때)
        }
    """
    current_slot = get_current_time_slot(now)
    slot_label = TIME_SLOT_TEMPLATES[current_slot]["label"]

    # product_id가 일치하고, 해당 시간대(current_slot)로 생성된 결과가 있는 이력을 최신순으로 탐색
    for entry in reversed(history):
        if entry.get("product_id") != product_id:
            continue
        matching_tones = [
            r for r in entry.get("results", [])
            if r.get("time_slot") == current_slot
        ]
        if matching_tones:
            return {
                "time_slot": current_slot,
                "time_slot_label": slot_label,
                "available": True,
                "tones": matching_tones,
            }

    return {
        "time_slot": current_slot,
        "time_slot_label": slot_label,
        "available": False,
        "tones": None,
    }
