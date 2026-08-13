from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.backend.schemas.video import (
    PublishStatus,
    VideoApprovalRequest,
    VideoCreateRequest,
    VideoCreateResponse,
    VideoJob,
)
from app.backend.services.store import HISTORY, PRODUCTS
from app.backend.services.video_workflow import (
    VideoWorkflowService,
    WorkflowConflict,
    WorkflowNotFound,
    WorkflowValidation,
)
from app.backend.api.deps import get_current_customer

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


def _workflow(request: Request) -> VideoWorkflowService:
    workflow = getattr(request.app.state, "video_workflow", None)
    if workflow is None:
        raise HTTPException(503, "영상 워크플로가 준비되지 않았습니다")
    return workflow


def _find_history_entry_for_result(result_id: str) -> dict | None:
    """result_id가 속한 HISTORY 항목(=그 결과를 생성한 고객사)을 찾는다."""
    for entry in HISTORY:
        for r in entry.get("results", []):
            if r.get("result_id") == result_id:
                return entry
    return None


def _ensure_owns_video_job(job: VideoJob, customer: dict) -> None:
    """
    VideoJob.product_id -> PRODUCTS[product_id].customer_id로 소유권을 확인한다.
    다른 고객사 video_job_id를 넣으면 실제 job이 있어도 "없는 것"과 동일하게 404 -
    조회는 물론 승인(유튜브 게시 트리거)·거절까지 다른 고객사가 할 수 있었던 문제
    (PR 리뷰에서 지적됨)를 여기서 막는다.
    """
    product = PRODUCTS.get(job.product_id)
    if not product or product.get("customer_id") != customer["customer_id"]:
        raise HTTPException(404, "video job not found")


@router.post("", response_model=VideoCreateResponse, status_code=202)
def create_video(
    req: VideoCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    customer: dict = Depends(get_current_customer),
) -> VideoCreateResponse:
    # job이 아직 없어서(생성 전) VideoJob.product_id로는 소유권을 확인할 수 없다 -
    # 대신 result_id가 속한 HISTORY 항목의 customer_id로 먼저 확인한다. 이 확인이
    # 없으면 다른 고객사 result_id로도 실제 영상 생성 job이 만들어져버린다.
    entry = _find_history_entry_for_result(req.result_id)
    if entry is not None and entry.get("customer_id") != customer["customer_id"]:
        raise HTTPException(404, "result_id에 해당하는 생성 결과를 찾을 수 없습니다")

    workflow = _workflow(request)
    try:
        job = workflow.create(req.result_id)
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except WorkflowValidation as exc:
        raise HTTPException(400, str(exc)) from exc
    except WorkflowConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 요청을 처리하지 못했습니다") from exc

    background_tasks.add_task(workflow.run_render, job.video_job_id)
    return VideoCreateResponse(
        video_job_id=job.video_job_id,
        render_status=job.render_status,
    )


@router.get("/{video_job_id}", response_model=VideoJob)
async def get_video(video_job_id: str, request: Request, customer: dict = Depends(get_current_customer)) -> VideoJob:
    workflow = _workflow(request)
    try:
        job = workflow.get(video_job_id)
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 상태를 조회하지 못했습니다") from exc
    _ensure_owns_video_job(job, customer)
    return job


@router.post(
    "/{video_job_id}/approve",
    response_model=VideoJob,
    status_code=202,
)
async def approve_video(
    video_job_id: str,
    req: VideoApprovalRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    customer: dict = Depends(get_current_customer),
) -> VideoJob:
    workflow = _workflow(request)
    try:
        existing = workflow.get(video_job_id)
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 상태를 조회하지 못했습니다") from exc
    _ensure_owns_video_job(existing, customer)  # 승인은 YouTube 게시까지 트리거하므로 특히 중요

    try:
        job = workflow.approve(
            video_job_id,
            activation_at=req.activation_at,
            publish_to_youtube=req.publish_to_youtube,
            pronunciation_confirmed=req.pronunciation_confirmed,
        )
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except WorkflowConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except WorkflowValidation as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 승인을 처리하지 못했습니다") from exc
    if job.publish_status is PublishStatus.PENDING:
        background_tasks.add_task(workflow.run_publish, job.video_job_id)
    return job


@router.post("/{video_job_id}/reject", response_model=VideoJob)
async def reject_video(video_job_id: str, request: Request, customer: dict = Depends(get_current_customer)) -> VideoJob:
    workflow = _workflow(request)
    try:
        existing = workflow.get(video_job_id)
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 상태를 조회하지 못했습니다") from exc
    _ensure_owns_video_job(existing, customer)

    try:
        return workflow.reject(video_job_id)
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except WorkflowConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 거절을 처리하지 못했습니다") from exc
