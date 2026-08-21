import time
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from app.backend.schemas.generation import (
    GenerationRequest,
    GenerationCreateResponse,
    GenerationResultResponse,
    CopyUpdateRequest,
)
from app.backend.services import overlay, store
from app.backend.services.store import PRODUCTS, JOBS, HISTORY
from app.backend.services.generation_service import generation_service
from app.backend.api.deps import get_current_customer
from app.prompt.templates import MAX_TIME_SLOTS_PER_REQUEST, estimate_seconds
from app.prompt.schemas import PromptRequest

router = APIRouter(prefix="/api/v1/generations", tags=["generations"])


def build_generation_plan(req: GenerationRequest, product: dict) -> list[PromptRequest]:
    """
    臾멸뎄 ?꾨＼?꾪듃 ?⑥쐞 = ?쒓컙? x ?? ?대?吏 ?앹꽦 ?묒뾽?됱? ??怨꾪쉷??媛???ぉ?먯꽌
    ?좏깮 鍮꾩쑉 ?섎쭔??蹂꾨룄濡?利앷??섎ŉ, 媛숈? 臾멸뎄瑜?鍮꾩쑉蹂??ㅼ씠?곕툕 ?앹꽦???ъ궗?⑺븳??
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
    # ?ㅻⅨ 怨좉컼???곹뭹 ID瑜??ｌ뼱??"?녿뒗 寃?怨??묎컳??404 - 議댁옱 ?щ? ?먯껜瑜??몄텧?섏? ?딅뒗??    if product.get("customer_id") != customer["customer_id"]:
        raise HTTPException(404, "product not found")
    if not req.time_slots:
        raise HTTPException(400, "select at least one time slot")
    if len(req.time_slots) > MAX_TIME_SLOTS_PER_REQUEST:
        raise HTTPException(
            400,
            f"??踰덉뿉 理쒕? {MAX_TIME_SLOTS_PER_REQUEST}媛??쒓컙?源뚯?留??좏깮 媛??(GPU ?湲곗뿴 蹂댄샇)",
        )

    # 以묐났 ?앹꽦 ?붿껌 諛⑹? - 媛숈? ?곹뭹??????대? 吏꾪뻾 以묒씤 job???덉쑝硫?409濡?嫄곕??쒕떎.
    # (?덈줈 ??留뚮뱾怨?湲곗〈 job??洹몃?濡??ъ궗?⑺븯??諛⑹떇???꾨땲??紐낆떆?곸쑝濡?留됰뒗 諛⑹떇?대떎 -
    #  ?꾨옒 detail??湲곗〈 job_id瑜?援ъ“?붾맂 ?꾨뱶濡??대젮以섏꽌, ?꾨줎?멸? ?먰븯硫?洹?job_id濡?    #  GET /jobs/{id}瑜??대쭅??吏꾪뻾 ?곹솴???댁뼱??蹂????덇쾶 ?쒕떎.)
    for existing_id, existing_job in JOBS.items():
        if existing_job["product_id"] == req.product_id and existing_job["status"] in ("queued", "processing"):
            raise HTTPException(
                409,
                detail={
                    "message": "?대? ?앹꽦 吏꾪뻾 以묒씤 ?붿껌???덉뒿?덈떎. ?꾨즺 ???ㅼ떆 ?쒕룄?댁＜?몄슂.",
                    "existing_job_id": existing_id,
                },
            )

    job_id = f"job_{uuid.uuid4().hex[:6]}"
    format_count = len(req.output_formats)
    total = len(req.tones) * len(req.time_slots) * format_count
    est = estimate_seconds(len(req.tones), len(req.time_slots), format_count)
    JOBS[job_id] = {
        "customer_id": customer["customer_id"],  # multi-tenant ?곗씠??寃⑸━
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
    # generation_service??USE_MOCK_GENERATION ?섍꼍蹂?섎줈 Mock/?ㅼ젣 紐⑤뜽 ?쒕쾭 以??좏깮??    background_tasks.add_task(run_generation, job_id)
    return GenerationCreateResponse(job_id=job_id, estimated_seconds=est)


async def run_generation(job_id: str) -> None:
    """
    generation_service留?援먯껜?섎㈃(Mock -> ModelServer) ???⑥닔????諛붾먮떎.
    ?ㅽ뙣/??꾩븘?껋? ?ш린???≪븘??job??'failed'濡??④린怨?UI媛 ?먮윭瑜?蹂댁뿬以????덇쾶 ?쒕떎.
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
            "customer_id": job["customer_id"],  # multi-tenant ?곗씠??寃⑸━
            "job_id": job_id,
            "product_id": job["product_id"],
            "created_at": time.time(),
            "results": job["result"],
            "favorite": False,  # S3 ??利먭꺼李얘린 (湲곕낯媛?false, ?좉?? PATCH /api/v1/history/{job_id}/favorite)
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
    """?뱀젙 ?앹꽦 寃곌낵??愿묎퀬 臾멸뎄瑜??섏젙?섍퀬 Job/History???④퍡 諛섏쁺?쒕떎."""
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

    source_images = target.get("source_images") or {}

    if not source_images:
        raise HTTPException(
            409,
            "臾멸뎄 ?녿뒗 ?먮낯 ?대?吏媛 ?놁뼱 ?섏젙?????놁뒿?덈떎. 愿묎퀬瑜??ㅼ떆 ?앹꽦?댁＜?몄슂.",
        )

    new_images: dict[str, str] = {}

    for output_format, source_url in source_images.items():
        try:
            background_image = overlay.load_output_image(source_url)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(
                409,
                f"?먮낯 ?대?吏瑜?遺덈윭?????놁뒿?덈떎: {output_format}",
            ) from exc

        rendered = overlay.generate_and_save(
            job_id=job_id,
            tone=target["tone"],
            time_slot=target.get("time_slot") or "default",
            headline=body.headline,
            subcopy=body.subcopy,
            output_formats=[output_format],
            background_image=background_image,
        )

        new_images.update(rendered)
    target["headline"] = body.headline
    target["subcopy"] = body.subcopy
    target["images"] = new_images

    for entry in HISTORY:
        if (
            entry.get("job_id") == job_id
            and entry.get("customer_id") == customer["customer_id"]
        ):
            for result in entry.get("results", []):
                if result.get("result_id") == body.result_id:
                    result["headline"] = body.headline
                    result["subcopy"] = body.subcopy
                    result["images"] = new_images.copy()
                    break
            break

    store.save()

    return {
        "job_id": job_id,
        "result_id": body.result_id,
        "headline": body.headline,
        "subcopy": body.subcopy,
    }
