from fastapi import Header, HTTPException

from app.backend.services import auth


async def get_current_customer(authorization: str | None = Header(None)) -> dict:
    """
    'Authorization: Bearer <token>' 헤더에서 세션 토큰을 꺼내 고객사를 확인한다.
    Products/Generations/History 라우터가 이 dependency로 요청자의 customer_id를 얻어
    자기 고객사 데이터만 보고 쓰게 한다 (multi-tenant 데이터 격리의 핵심).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "로그인이 필요합니다")
    token = authorization.removeprefix("Bearer ").strip()
    customer = auth.resolve_session(token)
    if not customer:
        raise HTTPException(401, "세션이 만료됐거나 유효하지 않습니다. 다시 로그인해주세요")
    return customer
