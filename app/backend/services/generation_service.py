"""
생성 로직을 서비스 인터페이스로 분리 - 나중에 R3 모델 서버가 완성되면
generation_service = LocalOverlayGenerationService() 한 줄만 바꾸면 된다 (UI/API 구조 변경 없음).
"""
import asyncio
import os
import uuid
from abc import ABC, abstractmethod

from app.backend.schemas.generation import GenerationRequest, ToneResult
from app.backend.services import copy_generator, overlay
from app.backend.services.store import JOBS


class GenerationService(ABC):
    @abstractmethod
    async def generate(self, job_id: str, req: GenerationRequest, product: dict) -> list[ToneResult]:
        """시간대 x 톤 조합별로 이미지+문구를 생성해서 ToneResult 리스트를 반환한다.
        진행 상태는 JOBS[job_id] (progress/completed_count/current_step)를 직접 갱신한다."""
        raise NotImplementedError


class LocalOverlayGenerationService(GenerationService):
    """
    R3 모델 서버 없이 완료 처리 (Gate 0용).
    문구(M3)는 copy_generator로 생성(USE_LLM_COPY 켜면 실제 LLM, 기본은 규칙 기반).
    배경 이미지는 model_server가 없으므로 톤별 placeholder이지만, 오버레이(M3)와
    규격별 실제 이미지 생성(S2)은 여기서 진짜로 동작한다 - model_server 연동 후에는
    배경 생성 부분만 실제 모델 호출로 교체하면 되고 오버레이 로직은 그대로 재사용된다.

    주의: build_ad_copy/generate_and_save는 동기(블로킹) 함수라 - OpenAI 동기 HTTP 호출,
    PIL 리사이즈/인코딩 - asyncio.to_thread로 감싸서 이벤트 루프를 막지 않게 한다.
    이걸 안 하면 생성이 도는 동안 GET /jobs/{id} 폴링 같은 다른 요청이 전부 멈춘다.
    """

    async def generate(self, job_id: str, req: GenerationRequest, product: dict) -> list[ToneResult]:
        from app.backend.api.generations import build_generation_plan  # 순환 import 방지용 지연 import

        job = JOBS[job_id]
        plan = build_generation_plan(req, product)
        results: list[ToneResult] = []

        for i, item in enumerate(plan):
            job["current_step"] = f"{item.time_slot}/{item.tone} 생성 중"

            headline, subcopy = await asyncio.to_thread(copy_generator.build_ad_copy, item)
            images = await asyncio.to_thread(
                overlay.generate_and_save,
                job_id=job_id,
                tone=item.tone,
                time_slot=item.time_slot or "default",
                headline=headline,
                subcopy=subcopy,
                output_formats=req.output_formats,
            )

            results.append(ToneResult(
                result_id=f"res_{uuid.uuid4().hex[:8]}",
                tone=item.tone,
                time_slot=item.time_slot,
                headline=headline,
                subcopy=subcopy,
                images=images,
            ))
            job["completed_count"] = i + 1
            job["progress"] = int((i + 1) / job["total_count"] * 100)

        return results


class ModelServerGenerationService(GenerationService):
    """
    R3 model_server 연동용 - 아직 미구현.
    TODO: app/backend/services/model_server_client.request_generation() 을
    plan(시간대x톤)마다 호출하고, 실패/타임아웃은 예외로 던져서
    run_generation()의 try/except가 job을 'failed'로 처리하게 한다.
    request_generation()은 이미 httpx.AsyncClient 기반이라 별도 to_thread 불필요.
    """
    async def generate(self, job_id: str, req: GenerationRequest, product: dict) -> list[ToneResult]:
        raise NotImplementedError("R3 model_server 연동 후 구현 예정")


# USE_MOCK_GENERATION=false 로 실제 모델 서버(R3 완성 후) 사용, 기본값은 true(Mock)
_use_mock = os.getenv("USE_MOCK_GENERATION", "true").strip().lower() != "false"
generation_service: GenerationService = LocalOverlayGenerationService() if _use_mock else ModelServerGenerationService()
