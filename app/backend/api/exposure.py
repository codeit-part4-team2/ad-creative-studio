from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.backend.services.store import HISTORY, PRODUCTS, VIDEO_JOBS
from app.backend.services.exposure import pick_exposure

router = APIRouter(prefix="/api/v1/exposure", tags=["exposure"])


@router.get("/{product_id}")
async def get_current_exposure(
    product_id: str,
    at: Optional[datetime] = Query(
        None, description="테스트/데모용 - 이 시각 기준으로 판정 (ISO 8601, 예: 2026-08-05T18:30:00+09:00). "
                            "생략하면 실제 현재 시각(KST) 기준."
    ),
):
    """
    지금 이 순간(또는 ?at= 로 지정한 시각) 노출해야 할 시간대 배너를 반환한다
    (S1 — 시간대별 제품 노출 알고리즘).
    `at`은 발표 데모에서 아침/출근/퇴근/심야 전환을 실제 시간을 기다리지 않고 보여주기 위한 용도.
    """
    if product_id not in PRODUCTS:
        raise HTTPException(404, "product not found")
    return pick_exposure(
        product_id,
        HISTORY,
        now=at,
        video_jobs=VIDEO_JOBS,
    )
