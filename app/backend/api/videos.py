from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backend.services import store
from app.backend.services.video_generation_service import (
    video_generation_service,
    RUSH_HOUR_SLOTS,
    find_tone_result,
)

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])

# TODO(follow-up): 지금은 인메모리 전용 - 서버 재시작하면 진행 중이던 쇼츠 job 상태가
# 유실된다. 데모 규모에선 무해하지만, store.py의 JOBS처럼 영속화하려면 여기도
# 같은 패턴(save()/load(), 좀비 job 정리)을 적용해야 한다.
VIDEO_JOBS: dict[str, dict] = {}


class VideoCreateRequest(BaseModel):
    result_id: str  # time_slot은 안 받는다 - result_id로 실제 결과를 찾아 그 시간대로 판정한다
    # (사용자가 result_id와 다른 time_slot을 잘못 보내는 경우를 원천 차단)


@router.post("")
async def create_video(req: VideoCreateRequest):
    """러시아워(출근/퇴근) 시간대 결과에 한해 쇼츠 생성을 요청한다."""
    entry, tone_result = find_tone_result(req.result_id)
    if not tone_result:
        raise HTTPException(404, "result_id에 해당하는 생성 결과를 찾을 수 없습니다")
    if tone_result.get("time_slot") not in RUSH_HOUR_SLOTS:
        raise HTTPException(400, "쇼츠 생성은 출근·퇴근 시간대 결과만 지원합니다.")

    result = await video_generation_service.create(req.result_id)
    if result.status == "failed":
        raise HTTPException(400, result.error_message or "쇼츠 생성 요청 실패")

    VIDEO_JOBS[result.job_id] = {
        "status": result.status,
        "video_url": result.video_url,
        "error_message": result.error_message,
        "result_id": req.result_id,
    }
    return {"video_job_id": result.job_id, "status": result.status}


@router.get("/{job_id}")
async def get_video_status(job_id: str):
    if job_id not in VIDEO_JOBS:
        raise HTTPException(404, "video job not found")

    result = await video_generation_service.get_status(job_id)
    VIDEO_JOBS[job_id].update(
        status=result.status, video_url=result.video_url, error_message=result.error_message,
    )

    if result.status == "completed" and result.video_url:
        # History의 해당 result에도 video_url을 남겨서, 새로고침해도 다시 볼 수 있게 한다.
        # store.save() 안 하면 서버 재시작 시(배포 갱신 등) 이미 완성된 쇼츠의 video_url이
        # History에서 사라진다 - 즐겨찾기 토글/생성완료와 동일한 영속화 규칙을 여기도 따른다.
        _, tone_result = find_tone_result(VIDEO_JOBS[job_id]["result_id"])
        if tone_result is not None:
            tone_result["video_url"] = result.video_url
            store.save()

    return {
        "video_job_id": job_id,
        "status": result.status,
        "video_url": result.video_url,
        "error_message": result.error_message,
    }
