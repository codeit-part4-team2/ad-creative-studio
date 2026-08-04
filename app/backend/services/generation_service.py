"""
생성 로직을 서비스 인터페이스로 분리 - 나중에 R3 모델 서버가 완성되면
generation_service = MockGenerationService() 한 줄만 바꾸면 된다 (UI/API 구조 변경 없음).
"""
import time
from abc import ABC, abstractmethod

from app.backend.schemas.generation import GenerationRequest, ToneResult
from app.prompt import builder as prompt_builder
from app.backend.services.store import JOBS


class GenerationService(ABC):
    @abstractmethod
    async def generate(self, job_id: str, req: GenerationRequest, product: dict) -> list[ToneResult]:
        """시간대 x 톤 조합별로 이미지+문구를 생성해서 ToneResult 리스트를 반환한다.
        진행 상태는 JOBS[job_id] (progress/completed_count/current_step)를 직접 갱신한다."""
        raise NotImplementedError


class MockGenerationService(GenerationService):
    """R3 모델 서버 없이 더미로 완료 처리 (Gate 0용)."""

    async def generate(self, job_id: str, req: GenerationRequest, product: dict) -> list[ToneResult]:
        from app.backend.api.generations import build_generation_plan  # 순환 import 방지용 지연 import

        job = JOBS[job_id]
        plan = build_generation_plan(req, product)
        results: list[ToneResult] = []

        for i, item in enumerate(plan):
            job["current_step"] = f"{item.time_slot}/{item.tone} 생성 중"
            prompt_result = prompt_builder.build(item)

            generated_image_url = "https://placehold.co/1000x1000"
            images = {fmt: generated_image_url for fmt in req.output_formats}

            results.append(ToneResult(
                tone=item.tone,
                time_slot=item.time_slot,
                headline=prompt_result.headline,
                subcopy=prompt_result.subcopy,
                images=images,
            ))
            job["completed_count"] = i + 1
            job["progress"] = int((i + 1) / job["total_count"] * 100)
            time.sleep(0.05)  # 데모용

        return results


class ModelServerGenerationService(GenerationService):
    """
    R3 model_server 연동용 - 아직 미구현.
    TODO: app/backend/services/model_server_client.request_generation() 을
    plan(시간대x톤)마다 호출하고, 실패/타임아웃은 예외로 던져서
    run_generation()의 try/except가 job을 'failed'로 처리하게 한다.
    """
    async def generate(self, job_id: str, req: GenerationRequest, product: dict) -> list[ToneResult]:
        raise NotImplementedError("R3 model_server 연동 후 구현 예정")


# 여기 한 줄만 바꾸면 실제 모델로 전환된다.
generation_service: GenerationService = MockGenerationService()
