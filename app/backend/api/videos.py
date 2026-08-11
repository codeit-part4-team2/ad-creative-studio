from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.backend.schemas.video import (
    PublishStatus,
    VideoApprovalRequest,
    VideoCreateRequest,
    VideoCreateResponse,
    VideoJob,
)
from app.backend.services.video_workflow import (
    VideoWorkflowService,
    WorkflowConflict,
    WorkflowNotFound,
    WorkflowValidation,
)


router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


def _workflow(request: Request) -> VideoWorkflowService:
    workflow = getattr(request.app.state, "video_workflow", None)
    if workflow is None:
        raise HTTPException(503, "영상 워크플로가 준비되지 않았습니다")
    return workflow


@router.post("", response_model=VideoCreateResponse, status_code=202)
async def create_video(
    req: VideoCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> VideoCreateResponse:
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
async def get_video(video_job_id: str, request: Request) -> VideoJob:
    workflow = _workflow(request)
    try:
        return workflow.get(video_job_id)
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 상태를 조회하지 못했습니다") from exc


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
) -> VideoJob:
    workflow = _workflow(request)
    try:
        job = workflow.approve(
            video_job_id,
            activation_at=req.activation_at,
            publish_to_youtube=req.publish_to_youtube,
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
async def reject_video(video_job_id: str, request: Request) -> VideoJob:
    workflow = _workflow(request)
    try:
        return workflow.reject(video_job_id)
    except WorkflowNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except WorkflowConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "영상 거절을 처리하지 못했습니다") from exc
