import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException

from app.backend.schemas.auth import (
    CustomerCreateRequest,
    CustomerResponse,
    LoginRequest,
    LoginResponse,
)
from app.backend.services import auth, store
from app.backend.api.deps import get_current_customer

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _to_response(customer: dict) -> CustomerResponse:
    return CustomerResponse(
        customer_id=customer["customer_id"],
        company_name=customer["company_name"],
        status=customer["status"],
        plan=customer["plan"],
    )


@admin_router.post("/customers", response_model=CustomerResponse, status_code=201)
async def create_customer(req: CustomerCreateRequest, x_admin_key: str | None = Header(None)):
    """계약된 고객사를 관리자가 등록 - ADMIN_API_KEY 헤더로만 보호 (팀 내부 도구 전용)."""
    if not auth.verify_admin_key(x_admin_key):
        raise HTTPException(403, "관리자 권한이 필요합니다")
    try:
        customer = auth.create_customer(req.customer_id, req.company_name, req.pin, req.plan)
    except ValueError as e:
        raise HTTPException(409, str(e))
    store.save()
    return _to_response(customer)


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    if auth.is_rate_limited(req.customer_id):
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요")
    # PBKDF2는 CPU 연산이라 to_thread로 돌려서 이벤트 루프를 막지 않는다
    token = await asyncio.to_thread(auth.verify_login, req.customer_id, req.pin)
    if not token:
        raise HTTPException(401, "고객 ID 또는 PIN이 올바르지 않습니다")
    customer = auth.CUSTOMERS[req.customer_id]
    return LoginResponse(token=token, customer=_to_response(customer))


@router.post("/logout", status_code=204)
async def logout(authorization: str | None = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        auth.logout(authorization.removeprefix("Bearer ").strip())


@router.get("/me", response_model=CustomerResponse)
async def me(customer: dict = Depends(get_current_customer)):
    return _to_response(customer)
