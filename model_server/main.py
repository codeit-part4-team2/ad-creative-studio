"""
model_server 진입점 (Mock 버전)

역할: app/backend가 호출하는 POST /infer 엔드포인트를 계약(docs/api_contract.md)에 맞는 형태로 미리 제공한다.
아직 실제 SDXL+ControlNet+IP-Adapter 모델은 연결되지 않았고, 정해진 응답 스키마만 그대로 돌려주는 더미 서버다.

목적: R4+R5(app/backend, 프론트엔드)가 실제 모델이 완성되기 전에도 UI/통합 테스트를 진행할 수 있게 하기 위함.

담당: R2(성치용, 유수빈), R3(김재헌)
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from app.prompt.schemas import ToneLiteral, TimeSlotLiteral

app = FastAPI()

class InferRequest(BaseModel):
    """app/backend가 /infer 호출 시 보내는 요청 형식 (docs/api_contract.md 기준)"""
    product_id: str
    product_image_url: str
    tone: ToneLiteral
    image_prompt: str
    negative_prompt: str
    time_slot: TimeSlotLiteral

class InferResponse(BaseModel):
    """/infer 응답 형식. 성공/실패 두 케이스를 하나의 모델로 표현한다.
    성공 시: status="done", generated_image_url/product_preserved/gen_time_sec 채워짐
    실패 시: status="failed", error_message 채워짐, generated_image_url=None
    """
    status: str
    generated_image_url: Optional[str]
    product_preserved: Optional[bool] = None
    gen_time_sec: Optional[float] = None
    error_message: Optional[str] = None


@app.post("/infer", response_model=InferResponse)
async def infer(request: InferRequest):
    # 테스트용: product_id가 "test_fail"이면 실패 응답을 흉내낸다.
    # (실제 모델 연결 전, R4+R5가 실패 케이스 처리 로직도 테스트할 수 있게 하기 위함)
    if request.product_id == "test_fail":
        return InferResponse(
            status="failed",
            generated_image_url=None,
            error_message="CUDA OOM",
        )

    # 정상 케이스: 실제 이미지 생성 없이 placeholder 이미지 URL을 반환한다.
    # TODO: 실제 모델(SDXL+ControlNet+IP-Adapter) 연결 후 이 부분 교체 필요
    
    return InferResponse(
        status="done",
        generated_image_url="https://placehold.co/1024x1024",
        product_preserved=True,
        gen_time_sec=1.0
    )
