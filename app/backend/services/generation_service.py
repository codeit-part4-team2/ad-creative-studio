"""
생성 로직을 서비스 인터페이스로 분리.
USE_MOCK_GENERATION=true(기본값) -> LocalOverlayGenerationService (Mock 배경)
USE_MOCK_GENERATION=false -> ModelServerGenerationService (R3 model_server 실제 호출)
파일 맨 아래 한 줄 조건으로 선택되며, UI/API 구조는 어느 쪽이든 동일하다.
"""
import asyncio
import os
import uuid
from abc import ABC, abstractmethod

from PIL import Image

from app.backend.schemas.generation import GenerationRequest, ToneResult
from app.backend.services import copy_generator, overlay
from app.backend.services.store import JOBS
from app.image_presets import get_image_preset
from app.prompt.schemas import PromptRequest


RUSH_HOUR_SLOTS = frozenset({"commute_am", "commute_pm"})


async def _prepare_copy_and_source(
    *,
    job_id: str,
    item: PromptRequest,
    copy_task: asyncio.Task[tuple[str, str]],
    source_image: Image.Image | None,
) -> tuple[str, str, str | None]:
    """Resolve one copy task and optionally persist its native 9:16 source."""
    if source_image is None:
        headline, subcopy = await copy_task
        return headline, subcopy, None

    time_slot = item.time_slot or "default"
    copy_result, source_image_url = await asyncio.gather(
        copy_task,
        asyncio.to_thread(
            overlay.save_source_image,
            job_id=job_id,
            tone=item.tone,
            time_slot=time_slot,
            image=source_image,
        ),
    )
    headline, subcopy = copy_result
    return headline, subcopy, source_image_url


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

        for item in plan:
            time_slot = item.time_slot or "default"
            copy_task = asyncio.create_task(
                asyncio.to_thread(copy_generator.build_ad_copy, item)
            )
            images: dict[str, str] = {}
            source_image_url: str | None = None

            for output_format in req.output_formats:
                job["current_step"] = (
                    f"{item.time_slot}/{item.tone}/{output_format} 생성 중"
                )
                preset = get_image_preset(output_format)
                background_image = overlay.create_placeholder_background(
                    item.tone,
                    preset.composite_size,
                )
                source_image = (
                    background_image
                    if item.time_slot in RUSH_HOUR_SLOTS
                    and output_format == "story_vertical"
                    else None
                )
                headline, subcopy, saved_source_url = (
                    await _prepare_copy_and_source(
                        job_id=job_id,
                        item=item,
                        copy_task=copy_task,
                        source_image=source_image,
                    )
                )
                if saved_source_url is not None:
                    source_image_url = saved_source_url
                rendered = await asyncio.to_thread(
                    overlay.generate_and_save,
                    job_id=job_id,
                    tone=item.tone,
                    time_slot=time_slot,
                    headline=headline,
                    subcopy=subcopy,
                    output_formats=[output_format],
                    background_image=background_image,
                )
                images.update(rendered)
                job["completed_count"] += 1
                job["progress"] = int(
                    job["completed_count"] / job["total_count"] * 100
                )

            results.append(ToneResult(
                result_id=f"res_{uuid.uuid4().hex[:8]}",
                tone=item.tone,
                time_slot=item.time_slot,
                headline=headline,
                subcopy=subcopy,
                source_image_url=source_image_url,
                images=images,
            ))

        return results


class ModelServerGenerationService(GenerationService):
    """
    R3 model_server 연동. docs/api_contract.md의 /infer 계약대로:
    이미지 프롬프트(영어)/negative_prompt는 prompt_builder가 만들고, model_server는
    "배경만" 생성해서 URL로 돌려준다 (제품 보존은 R2/R3 담당) - 우리는 그 배경 위에
    LocalOverlayGenerationService와 완전히 동일한 오버레이/규격 로직을 그대로 적용한다.
    문구(M3)는 동일하게 copy_generator를 쓴다 - Mock/Real이 배경 생성 방식만 다르고
    나머지 파이프라인은 100% 재사용된다.

    실패(status: failed)/타임아웃(model_server_client의 120초)은 예외로 던져서
    run_generation()의 try/except가 job을 'failed'로 처리하게 한다.
    """

    async def generate(self, job_id: str, req: GenerationRequest, product: dict) -> list[ToneResult]:
        from app.backend.api.generations import build_generation_plan  # 순환 import 방지용 지연 import
        from app.backend.services import model_server_client
        from app.prompt import builder as prompt_builder

        job = JOBS[job_id]
        plan = build_generation_plan(req, product)
        results: list[ToneResult] = []

        for item in plan:
            time_slot = item.time_slot or "default"

            prompt_result = prompt_builder.build(item)  # image_prompt(영어)/negative_prompt
            copy_task = asyncio.create_task(
                asyncio.to_thread(copy_generator.build_ad_copy, item)
            )
            images: dict[str, str] = {}
            source_image_url: str | None = None

            for output_format in req.output_formats:
                job["current_step"] = (
                    f"{item.time_slot}/{item.tone}/{output_format} 생성 중"
                )
                response = await model_server_client.request_generation(
                    product_id=req.product_id,
                    # client가 backend 기준 상대경로를 BACKEND_PUBLIC_URL과 결합해
                    # model_server에서 접근 가능한 절대 URL로 변환한다.
                    product_image_url=product["image_url"],
                    tone=item.tone,
                    image_prompt=prompt_result.image_prompt,
                    negative_prompt=prompt_result.negative_prompt,
                    time_slot=item.time_slot,
                    output_format=output_format,
                )

                if response.get("status") != "done":
                    raise RuntimeError(
                        "model_server 생성 실패 "
                        f"({item.tone}/{item.time_slot}/{output_format}): "
                        f"{response.get('error_message', '알 수 없는 오류')}"
                    )

                background_image = await model_server_client.fetch_generated_image(
                    response["generated_image_url"]
                )
                source_image = (
                    background_image
                    if item.time_slot in RUSH_HOUR_SLOTS
                    and output_format == "story_vertical"
                    else None
                )
                headline, subcopy, saved_source_url = (
                    await _prepare_copy_and_source(
                        job_id=job_id,
                        item=item,
                        copy_task=copy_task,
                        source_image=source_image,
                    )
                )
                if saved_source_url is not None:
                    source_image_url = saved_source_url
                rendered = await asyncio.to_thread(
                    overlay.generate_and_save,
                    job_id=job_id,
                    tone=item.tone,
                    time_slot=time_slot,
                    headline=headline,
                    subcopy=subcopy,
                    output_formats=[output_format],
                    background_image=background_image,
                )
                images.update(rendered)
                job["completed_count"] += 1
                job["progress"] = int(
                    job["completed_count"] / job["total_count"] * 100
                )

            results.append(ToneResult(
                result_id=f"res_{uuid.uuid4().hex[:8]}",
                tone=item.tone,
                time_slot=item.time_slot,
                headline=headline,
                subcopy=subcopy,
                source_image_url=source_image_url,
                images=images,
            ))

        return results


# USE_MOCK_GENERATION=false 로 실제 모델 서버(R3 완성 후) 사용, 기본값은 true(Mock)
_use_mock = os.getenv("USE_MOCK_GENERATION", "true").strip().lower() != "false"
generation_service: GenerationService = LocalOverlayGenerationService() if _use_mock else ModelServerGenerationService()
