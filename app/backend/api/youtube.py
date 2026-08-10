from fastapi import APIRouter, HTTPException, Request

from app.backend.schemas.video import YouTubeStatusResponse
from app.backend.services.video_workflow import VideoWorkflowService


router = APIRouter(prefix="/api/v1/youtube", tags=["youtube"])


@router.get("/status", response_model=YouTubeStatusResponse)
async def youtube_status(request: Request) -> YouTubeStatusResponse:
    workflow: VideoWorkflowService | None = getattr(
        request.app.state,
        "video_workflow",
        None,
    )
    if workflow is None:
        raise HTTPException(503, "영상 워크플로가 준비되지 않았습니다")
    try:
        return YouTubeStatusResponse.model_validate(workflow.youtube_status())
    except Exception as exc:
        raise HTTPException(500, "YouTube 상태를 조회하지 못했습니다") from exc
