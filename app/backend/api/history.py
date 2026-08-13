from fastapi import APIRouter, HTTPException, Query, Depends

from app.backend.services import store
from app.backend.services.store import HISTORY
from app.backend.api.deps import get_current_customer

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
async def get_history(
    favorite_only: bool = Query(False, description="즐겨찾기만 조회 (S3)"),
    customer: dict = Depends(get_current_customer),
):
    own = [h for h in HISTORY if h.get("customer_id") == customer["customer_id"]]
    if favorite_only:
        return [h for h in own if h.get("favorite")]
    return own


@router.patch("/{job_id}/favorite")
async def toggle_favorite(job_id: str, customer: dict = Depends(get_current_customer)):
    """즐겨찾기 토글 (S3 — 생성 이력·즐겨찾기)."""
    for entry in HISTORY:
        if entry["job_id"] == job_id and entry.get("customer_id") == customer["customer_id"]:
            entry["favorite"] = not entry.get("favorite", False)
            store.save()
            return {"job_id": job_id, "favorite": entry["favorite"]}
    raise HTTPException(404, "history entry not found")
