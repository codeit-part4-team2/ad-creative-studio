"""
평가 지표 계산 함수. eval_criteria.md 기준.
1순위(Product Preservation)는 R2/R3가 model_server 응답의 product_preserved에서 1차 판단하고,
여기서는 서비스 단(R4+R5) 로그를 모아 집계하는 용도로 쓴다.

TODO: R1(안은남)의 평가 하네스 설계에 맞춰 세부 구현 - 지금은 인터페이스만 고정.
"""
from dataclasses import dataclass


@dataclass
class GenerationLogEntry:
    job_id: str
    tone: str
    time_slot: str
    product_preserved: bool
    gen_time_sec: float


def product_preservation_rate(entries: list[GenerationLogEntry]) -> float:
    """제품 보존율 = product_preserved=True 비율 (1순위 지표)."""
    if not entries:
        return 0.0
    return sum(1 for e in entries if e.product_preserved) / len(entries)


def average_generation_time(entries: list[GenerationLogEntry]) -> float:
    if not entries:
        return 0.0
    return sum(e.gen_time_sec for e in entries) / len(entries)


def generation_time_by_time_slot(entries: list[GenerationLogEntry]) -> dict[str, float]:
    """시간대별 평균 생성 시간 - Before/After 최적화 비교용 (R3)."""
    by_slot: dict[str, list[float]] = {}
    for e in entries:
        by_slot.setdefault(e.time_slot, []).append(e.gen_time_sec)
    return {slot: sum(times) / len(times) for slot, times in by_slot.items()}
