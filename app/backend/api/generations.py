import time
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.backend.schemas.generation import (
    GenerationRequest,
    GenerationCreateResponse,
    GenerationResultResponse,
    CopyUpdateRequest,
)
from app.backend.services import store
from app.backend.services.store import PRODUCTS, JOBS, HISTORY
from app.backend.services.generation_service import generation_service
from app.prompt.templates import MAX_TIME_SLOTS_PER_REQUEST, estimate_seconds
from app.prompt.schemas import PromptRequest

router = APIRouter(prefix="/api/v1/generations", tags=["generations"])


def build_generation_plan(req: GenerationRequest, product: dict) -> list[PromptRequest]:
    """
    모델이 실제로 생성해야 하는 단위 = 시간대 x 톤 (출력 규격은 후처리 조건이라 여기 안 곱한다).
    시간대 3개 x 톤 4개 = 12개가 생성 대상이고, 각 결과에서 규격 3종을 PIL로 파생한다.
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
async def create_generation(req: GenerationRequest, background_tasks: BackgroundTasks):
    if req.product_id not in PRODUCTS:
        raise HTTPException(404, "product not found")
    if not req.time_slots:
        raise HTTPException(400, "select at least one time slot")
    if len(req.time_slots) > MAX_TIME_SLOTS_PER_REQUEST:
        raise HTTPException(
            400,
            f"한 번에 최대 {MAX_TIME_SLOTS_PER_REQUEST}개 시간대까지만 선택 가능 (GPU 대기열 보호)",
        )

    # 중복 생성 요청 방지 - 같은 상품에 대해 이미 진행 중인 job이 있으면 새로 안 만들고 그걸 반환
    for existing_id, existing_job in JOBS.items():
        if existing_job["product_id"] == req.product_id and existing_job["status"] in ("queued", "processing"):
            raise HTTPException(
                409,
                f"이미 생성 진행 중인 요청이 있습니다 (job_id={existing_id}). 완료 후 다시 시도해주세요.",
            )

    job_id = f"job_{uuid.uuid4().hex[:6]}"
    total = len(req.tones) * len(req.time_slots)  # 시간대 x 톤만 (규격 곱하지 않음)
    est = estimate_seconds(len(req.tones), len(req.time_slots))
    JOBS[job_id] = {
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
async def get_generation_result(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["status"] != "completed":
        raise HTTPException(409, "job not finished yet")
    return GenerationResultResponse(job_id=job_id, status="completed", results=job["result"])


@router.patch("/{job_id}/copy")
async def update_copy(job_id: str, body: CopyUpdateRequest):
    """
    이미지는 재생성하지 않고 문구만 수정 (PIL 오버레이 전략의 핵심 이점, 결정 7).
    MVP 방식: job_id 단위로 통일 (기존 generation_id/job_id 혼용 수정).
    TODO: 결과가 여러 개(톤x시간대)이므로, 추후 결과별 result_id를 부여해
    PATCH /api/v1/results/{result_id}/copy 로 세분화하는 게 더 정확함.
    """
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "generation not found")
    # TODO: overlay.overlay_copy(...) 재실행해서 이미지에 새 문구만 다시 얹기
    return {"headline": body.headline, "subcopy": body.subcopy}
