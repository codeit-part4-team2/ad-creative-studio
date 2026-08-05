from fastapi import APIRouter, HTTPException, Query

from app.backend.services.store import HISTORY

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
async def get_history(favorite_only: bool = Query(False, description="즐겨찾기만 조회 (S3)")):
    if favorite_only:
        return [h for h in HISTORY if h.get("favorite")]
    return HISTORY


@router.patch("/{job_id}/favorite")
async def toggle_favorite(job_id: str):
    """즐겨찾기 토글 (S3 — 생성 이력·즐겨찾기)."""
    for entry in HISTORY:
        if entry["job_id"] == job_id:
            entry["favorite"] = not entry.get("favorite", False)
            return {"job_id": job_id, "favorite": entry["favorite"]}
    raise HTTPException(404, "history entry not found")
