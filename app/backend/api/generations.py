import time
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from app.backend.schemas.generation import (
    GenerationRequest,
    GenerationCreateResponse,
    GenerationResultResponse,
    CopyUpdateRequest,
)
from app.backend.services import store
from app.backend.services.store import PRODUCTS, JOBS, HISTORY
from app.backend.services.generation_service import generation_service
from app.backend.api.deps import get_current_customer
from app.prompt.templates import MAX_TIME_SLOTS_PER_REQUEST, estimate_seconds
from app.prompt.schemas import PromptRequest

router = APIRouter(prefix="/api/v1/generations", tags=["generations"])


def build_generation_plan(req: GenerationRequest, product: dict) -> list[PromptRequest]:
    """
    문구 프롬프트 단위 = 시간대 x 톤. 이미지 생성 작업량은 이 계획의 각 항목에서
    선택 비율 수만큼 별도로 증가하며, 같은 문구를 비율별 네이티브 생성에 재사용한다.
    """
    plan = []
    for time_slot in req.time_slots:
        for tone in req.tones:
            plan.append(PromptRequest(
                product_name=product["product_name"],
                price=product.get("price"),
                selling_points=product.get("selling_points", []),
                tone=tone,
                time_slot=time_slot,
            ))
    return plan


@router.post("", response_model=GenerationCreateResponse, status_code=202)
async def create_generation(req: GenerationRequest, background_tasks: BackgroundTasks, customer: dict = Depends(get_current_customer)):
    product = PRODUCTS.get(req.product_id)
    if not product:
        raise HTTPException(404, "product not found")
    # 다른 고객사 상품 ID를 넣어도 "없는 것"과 똑같이 404 - 존재 여부 자체를 노출하지 않는다
    if product.get("customer_id") != customer["customer_id"]:
        raise HTTPException(404, "product not found")
    if not req.time_slots:
        raise HTTPException(400, "select at least one time slot")
    if len(req.time_slots) > MAX_TIME_SLOTS_PER_REQUEST:
        raise HTTPException(
            400,
            f"한 번에 최대 {MAX_TIME_SLOTS_PER_REQUEST}개 시간대까지만 선택 가능 (GPU 대기열 보호)",
        )

    # 중복 생성 요청 방지 - 같은 상품에 대해 이미 진행 중인 job이 있으면 409로 거부한다.
    # (새로 안 만들고 기존 job을 그대로 재사용하는 방식이 아니라 명시적으로 막는 방식이다 -
    #  아래 detail에 기존 job_id를 구조화된 필드로 내려줘서, 프론트가 원하면 그 job_id로
    #  GET /jobs/{id}를 폴링해 진행 상황을 이어서 볼 수 있게 한다.)
    for existing_id, existing_job in JOBS.items():
        if existing_job["product_id"] == req.product_id and existing_job["status"] in ("queued", "processing"):
            raise HTTPException(
                409,
                detail={
                    "message": "이미 생성 진행 중인 요청이 있습니다. 완료 후 다시 시도해주세요.",
                    "existing_job_id": existing_id,
                },
            )

    job_id = f"job_{uuid.uuid4().hex[:6]}"
    format_count = len(req.output_formats)
    total = len(req.tones) * len(req.time_slots) * format_count
    est = estimate_seconds(len(req.tones), len(req.time_slots), format_count)
    JOBS[job_id] = {
        "customer_id": customer["customer_id"],  # multi-tenant 데이터 격리
        "status": "queued",
        "progress": 0,
        "current_step": None,
        "completed_count": 0,
        "total_count": total,
        "estimated_seconds": est,
        "product_id": req.product_id,
        "request": req.model_dump(),
        "result": None,
        "error_message": None,
    }
    store.save()
    # generation_service는 USE_MOCK_GENERATION 환경변수로 Mock/실제 모델 서버 중 선택됨
    background_tasks.add_task(run_generation, job_id)
    return GenerationCreateResponse(job_id=job_id, estimated_seconds=est)


async def run_generation(job_id: str) -> None:
    """
    generation_service만 교체하면(Mock -> ModelServer) 이 함수는 안 바뀐다.
    실패/타임아웃은 여기서 잡아서 job을 'failed'로 남기고 UI가 에러를 보여줄 수 있게 한다.
    """
    job = JOBS[job_id]
    try:
        job["status"] = "processing"
        req = GenerationRequest(**job["request"])
        product = PRODUCTS[job["product_id"]]

        results = await generation_service.generate(job_id, req, product)

        job["result"] = [r.model_dump() for r in results]
        job["status"] = "completed"
        job["progress"] = 100
        job["current_step"] = None

        HISTORY.append({
            "customer_id": job["customer_id"],  # multi-tenant 데이터 격리
            "job_id": job_id,
            "product_id": job["product_id"],
            "created_at": time.time(),
            "results": job["result"],
            "favorite": False,  # S3 — 즐겨찾기 (기본값 false, 토글은 PATCH /api/v1/history/{job_id}/favorite)
        })
    except Exception as exc:
        job["status"] = "failed"
        job["error_message"] = str(exc)
        job["current_step"] = None
    finally:
        store.save()


@router.get("/{job_id}", response_model=GenerationResultResponse)
async def get_generation_result(job_id: str, customer: dict = Depends(get_current_customer)):
    job = JOBS.get(job_id)
    if not job or job.get("customer_id") != customer["customer_id"]:
        raise HTTPException(404, "job not found")
    if job["status"] != "completed":
        raise HTTPException(409, "job not finished yet")
    return GenerationResultResponse(job_id=job_id, status="completed", results=job["result"])


@router.patch("/{job_id}/copy")
async def update_copy(
    job_id: str,
    body: CopyUpdateRequest,
    customer: dict = Depends(get_current_customer),
):
    """특정 생성 결과의 광고 문구를 수정하고 Job/History에 함께 반영한다."""
    job = JOBS.get(job_id)

    if not job or job.get("customer_id") != customer["customer_id"]:
        raise HTTPException(404, "generation not found")

    if job.get("status") != "completed" or not job.get("result"):
        raise HTTPException(409, "generation not completed")

    target = next(
        (
            result
            for result in job["result"]
            if result.get("result_id") == body.result_id
        ),
        None,
    )

    if target is None:
        raise HTTPException(404, "result not found")

    target["headline"] = body.headline
    target["subcopy"] = body.subcopy

    for entry in HISTORY:
        if (
            entry.get("job_id") == job_id
            and entry.get("customer_id") == customer["customer_id"]
        ):
            for result in entry.get("results", []):
                if result.get("result_id") == body.result_id:
                    result["headline"] = body.headline
                    result["subcopy"] = body.subcopy
                    break
            break

    store.save()

    return {
        "job_id": job_id,
        "result_id": body.result_id,
        "headline": body.headline,
        "subcopy": body.subcopy,
    }