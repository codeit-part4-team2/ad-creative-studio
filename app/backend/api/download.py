"""
다운로드 실제 구현 (통합 체크리스트 7·9번 갭).
생성 결과 이미지는 overlay.generate_and_save()가 data/outputs/ 하위에 실제 파일로 저장하고
/files/... 정적 URL로 노출하는데(정확한 하위 경로는 OUTPUT_DIR 위치에 따라 동적으로 정해짐),
그 URL을 실제 파일로 매핑해서 다운로드 응답을 만든다.
"""
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.backend.services.store import JOBS

router = APIRouter(prefix="/api/v1/download", tags=["download"])

OUTPUT_ROOT = Path("data/outputs").resolve()


def _url_to_path(url: str) -> Path:
    """
    '/files/outputs/xxx.png' -> data/outputs/xxx.png 실제 경로로 변환.
    URL은 지금은 우리 서비스 내부 생성 결과에서만 나오지만, 방어적으로
    data/outputs/ 하위(그 자체 포함)를 벗어나는 경로(예: '../../' 조작)는 거부한다.
    candidate == OUTPUT_ROOT(디렉터리 자체)도 거부한다 - 통과시키면 FileResponse가
    디렉터리를 열려다 500을 낸다.
    """
    candidate = (Path("data") / url.removeprefix("/files/")).resolve()
    if OUTPUT_ROOT not in candidate.parents:
        raise HTTPException(400, "invalid output path")
    return candidate


def _get_completed_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["status"] != "completed":
        raise HTTPException(409, "job not finished yet")
    return job


@router.get("/{job_id}")
async def download_one(job_id: str, tone: str, output_format: str):
    """특정 톤·규격 이미지 1개 다운로드. (`format`은 파이썬 빌트인이라 output_format으로 명명)"""
    job = _get_completed_job(job_id)
    for tone_result in job["result"]:
        if tone_result["tone"] == tone and output_format in tone_result["images"]:
            file_path = _url_to_path(tone_result["images"][output_format])
            if not file_path.exists():
                raise HTTPException(404, "file not found on disk")
            return FileResponse(
                file_path,
                media_type="image/png",
                filename=f"{job_id}_{tone}_{output_format}.png",
            )
    raise HTTPException(404, "matching tone/format not found in this job")


@router.get("/{job_id}/all")
async def download_all(job_id: str):
    """이 job의 모든 톤×규격 이미지를 ZIP으로 묶어서 한 번에 다운로드."""
    job = _get_completed_job(job_id)

    buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for tone_result in job["result"]:
            tone = tone_result["tone"]
            for fmt, url in tone_result["images"].items():
                file_path = _url_to_path(url)
                if file_path.exists():
                    zf.write(file_path, arcname=f"{tone}_{fmt}.png")
                    file_count += 1

    if file_count == 0:
        # 디스크에서 파일이 사라진 경우(예: 수동 삭제) 빈 ZIP을 200으로 조용히 주면 안 됨
        raise HTTPException(404, "no downloadable files found for this job")

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={job_id}_all.zip"},
    )
