from fastapi import APIRouter

from app.backend.services import openai_client

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


@router.get("")
async def get_usage():
    return openai_client.get_usage()
