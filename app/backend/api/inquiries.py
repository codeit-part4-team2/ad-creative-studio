import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from app.backend.api.deps import get_current_customer
from app.backend.schemas.inquiry import (
    InquiryAnswerCreate,
    InquiryCreate,
    InquiryResponse,
)
from app.backend.services import auth, store
from app.backend.services.store import INQUIRIES


router = APIRouter(prefix="/api/v1/inquiries", tags=["inquiries"])

admin_router = APIRouter(
    prefix="/api/v1/admin/inquiries",
    tags=["admin-inquiries"],
)


@router.get("", response_model=list[InquiryResponse])
async def get_inquiries(
    customer: dict = Depends(get_current_customer),
):
    """로그인한 고객사의 문의만 최신순으로 조회한다."""
    own = [
        inquiry
        for inquiry in INQUIRIES
        if inquiry.get("customer_id") == customer["customer_id"]
    ]

    return sorted(
        own,
        key=lambda inquiry: inquiry["created_at"],
        reverse=True,
    )


@router.post(
    "",
    response_model=InquiryResponse,
    status_code=201,
)
async def create_inquiry(
    body: InquiryCreate,
    customer: dict = Depends(get_current_customer),
):
    inquiry = {
        "inquiry_id": f"inq_{uuid.uuid4().hex[:12]}",
        "customer_id": customer["customer_id"],
        "company_name": customer["company_name"],
        "title": body.title,
        "content": body.content,
        "status": "waiting",
        "answer": None,
        "answered_at": None,
        "created_at": time.time(),
    }

    INQUIRIES.append(inquiry)
    store.save()

    return inquiry


@router.get(
    "/{inquiry_id}",
    response_model=InquiryResponse,
)
async def get_inquiry(
    inquiry_id: str,
    customer: dict = Depends(get_current_customer),
):
    """일반 고객은 자신의 문의만 볼 수 있다."""
    for inquiry in INQUIRIES:
        if (
            inquiry["inquiry_id"] == inquiry_id
            and inquiry.get("customer_id") == customer["customer_id"]
        ):
            return inquiry

    # 다른 고객사의 inquiry_id가 존재하는지조차 노출하지 않는다.
    raise HTTPException(status_code=404, detail="inquiry not found")


@admin_router.get(
    "",
    response_model=list[InquiryResponse],
)
async def get_all_inquiries(
    x_admin_key: str | None = Header(None),
):
    """운영자는 ADMIN_API_KEY를 통해 전체 문의를 조회한다."""
    if not auth.verify_admin_key(x_admin_key):
        raise HTTPException(
            status_code=403,
            detail="관리자 권한이 필요합니다",
        )

    return sorted(
        INQUIRIES,
        key=lambda inquiry: inquiry["created_at"],
        reverse=True,
    )


@admin_router.post(
    "/{inquiry_id}/answer",
    response_model=InquiryResponse,
)
async def answer_inquiry(
    inquiry_id: str,
    body: InquiryAnswerCreate,
    x_admin_key: str | None = Header(None),
):
    """운영자만 문의에 답변할 수 있다."""
    if not auth.verify_admin_key(x_admin_key):
        raise HTTPException(
            status_code=403,
            detail="관리자 권한이 필요합니다",
        )

    for inquiry in INQUIRIES:
        if inquiry["inquiry_id"] != inquiry_id:
            continue

        inquiry["answer"] = body.answer
        inquiry["status"] = "answered"
        inquiry["answered_at"] = time.time()

        store.save()

        return inquiry

    raise HTTPException(
        status_code=404,
        detail="inquiry not found",
    )