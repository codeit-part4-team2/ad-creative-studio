"""
쇼츠(러시아워 한정 짧은 광고 영상) 생성 서비스 인터페이스.

경계: 우리 쪽은 result_id -> scenes 조립 + 어댑터 인터페이스만 갖춘다.
실제 TTS·영상 렌더링은 쇼츠 담당자의 generate_rush_hour_short(scenes, output_filename)가
맡는다 (원본: https://github.com/Adam-1228/youtube-shorts-automation 을 감싼 형태).
합의된 계약: scenes(list[dict], 각 항목 text 필수·duration/narration/image_path 선택),
output_filename -> 완성된 MP4 로컬 경로(9:16, 1080x1920, ~30초) 반환.

generation_service.py와 동일한 패턴(GenerationService 어댑터, Mock->실제 한 줄 전환)을 따른다.
"""
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.backend.services.store import HISTORY, PRODUCTS

RUSH_HOUR_SLOTS = {"commute_am", "commute_pm"}
VIDEO_DIR = Path("data/videos")  # 모듈 속성으로 둬서 테스트에서 monkeypatch로 격리 가능하게 함


@dataclass
class VideoGenerationResult:
    job_id: str
    status: str  # "queued" | "processing" | "completed" | "failed"
    video_url: Optional[str] = None
    error_message: Optional[str] = None


def find_tone_result(result_id: str) -> tuple[Optional[dict], Optional[dict]]:
    """result_id로 History 전체를 뒤져서 (history_entry, tone_result)를 찾는다."""
    for entry in HISTORY:
        for r in entry.get("results", []):
            if r.get("result_id") == result_id:
                return entry, r
    return None, None


def build_scenes_from_result(result_id: str) -> list[dict]:
    """
    result_id -> 상품정보 조회 -> 광고 이미지/문구/셀링포인트 조회 -> scenes 조립.
    담당자의 generate_rush_hour_short()에 넘길 최종 입력이 여기서 만들어진다.
    """
    entry, tone_result = find_tone_result(result_id)
    if not tone_result:
        raise ValueError(f"result_id={result_id}에 해당하는 생성 결과를 찾을 수 없습니다")

    product = PRODUCTS.get(entry["product_id"], {}) if entry else {}
    image_path = None
    if tone_result.get("images"):
        first_url = next(iter(tone_result["images"].values()))
        if first_url.startswith("/files/"):
            image_path = "data/" + first_url.removeprefix("/files/")

    scenes = [{
        "text": tone_result["headline"],
        "narration": tone_result["headline"],
        "duration": 6,
        "image_path": image_path,
    }]
    selling_points = product.get("selling_points")
    if selling_points:
        scenes.append({
            "text": tone_result["subcopy"],
            "narration": ", ".join(selling_points),
            "duration": 6,
            "image_path": image_path,
        })
    return scenes


class VideoGenerationService(ABC):
    @abstractmethod
    async def create(self, result_id: str) -> VideoGenerationResult:
        """
        time_slot을 인자로 안 받는다 - 사용자가 result_id와 다른 time_slot을 잘못
        보내는 경우(예: commute_pm 광고인데 commute_am을 보냄)를 원천 차단하기 위해,
        result_id로 실제 결과를 찾아 거기 저장된 time_slot으로 러시아워 여부를 판정한다
        (호출부 app/backend/api/videos.py의 create_video 참고).
        """
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, job_id: str) -> VideoGenerationResult:
        raise NotImplementedError


class MockVideoGenerationService(VideoGenerationService):
    """쇼츠 담당자 함수 완성 전에도 요청~조회 흐름을 검증할 수 있게 하는 Mock."""

    async def create(self, result_id: str) -> VideoGenerationResult:
        _, tone_result = find_tone_result(result_id)
        if not tone_result:
            return VideoGenerationResult(
                job_id="", status="failed",
                error_message=f"result_id={result_id}에 해당하는 생성 결과를 찾을 수 없습니다",
            )
        if tone_result.get("time_slot") not in RUSH_HOUR_SLOTS:
            return VideoGenerationResult(
                job_id="", status="failed",
                error_message=f"쇼츠는 출근/퇴근 시간대 결과만 지원합니다 (실제: {tone_result.get('time_slot')})",
            )
        try:
            build_scenes_from_result(result_id)  # scenes 조립 자체는 Mock에서도 실제로 검증
        except ValueError as exc:
            return VideoGenerationResult(job_id="", status="failed", error_message=str(exc))

        job_id = f"video_mock_{uuid.uuid4().hex[:6]}"
        return VideoGenerationResult(job_id=job_id, status="queued")

    async def get_status(self, job_id: str) -> VideoGenerationResult:
        VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        placeholder = VIDEO_DIR / "mock_short.mp4"
        if not placeholder.exists():
            placeholder.write_bytes(b"")  # 실제 재생은 안 되는 자리표시자 - 연동 배관 검증용
        return VideoGenerationResult(job_id=job_id, status="completed", video_url="/files/videos/mock_short.mp4")


class RushHourVideoGenerationService(VideoGenerationService):
    """
    실제 연동 자리. 쇼츠 담당자가 generate_rush_hour_short(scenes, output_filename)를
    제공하면, build_scenes_from_result()로 만든 scenes를 넘기고 결과 MP4 경로를 받아
    data/videos/ 밑으로 정리한 뒤 /files/videos/... URL로 반환하면 된다.
    담당자 함수의 실제 파라미터명/반환형식이 확정되면 여기서 맞춰 감싼다 (계약이
    다르면 이 클래스만 고치면 되고, VideoGenerationService 인터페이스는 안 바뀐다).
    """
    async def create(self, result_id: str) -> VideoGenerationResult:
        raise NotImplementedError("쇼츠 담당자 generate_rush_hour_short() 연동 후 구현 예정")

    async def get_status(self, job_id: str) -> VideoGenerationResult:
        raise NotImplementedError("쇼츠 담당자 generate_rush_hour_short() 연동 후 구현 예정")


# USE_MOCK_VIDEO=false 로 실제 쇼츠 서비스 사용, 기본값은 true(Mock)
_use_mock_video = os.getenv("USE_MOCK_VIDEO", "true").strip().lower() != "false"
video_generation_service: VideoGenerationService = (
    MockVideoGenerationService() if _use_mock_video else RushHourVideoGenerationService()
)
