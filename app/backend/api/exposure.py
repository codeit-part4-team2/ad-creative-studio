from fastapi import APIRouter, HTTPException

from app.backend.services.store import PRODUCTS, HISTORY
from app.backend.services.exposure import pick_exposure

router = APIRouter(prefix="/api/v1/exposure", tags=["exposure"])


@router.get("/{product_id}")
async def get_current_exposure(product_id: str):
    """지금 이 순간 노출해야 할 시간대 배너를 반환한다 (S1 — 시간대별 제품 노출 알고리즘)."""
    if product_id not in PRODUCTS:
        raise HTTPException(404, "product not found")
    return pick_exposure(product_id, HISTORY)
