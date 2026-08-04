from fastapi import APIRouter

from app.backend.services.store import HISTORY

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
async def get_history():
    return HISTORY
