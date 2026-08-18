from typing import Literal, Optional
from pydantic import BaseModel, Field

ToneLiteral = Literal["emotional", "modern", "practical", "premium"]

# PM 승인: 3종(morning/afternoon/evening) -> 러시아워 반영 6종으로 확장
TimeSlotLiteral = Literal[
    "morning", "commute_am", "afternoon", "commute_pm", "evening", "late_night"
]

class PromotionInfo(BaseModel):
    """
    사용자가 실제로 입력한 프로모션 정보만 반영한다.
    입력이 없으면 "타임딜/카운트다운/할인율" 같은 문구를 임의로 만들지 않는다
    (재판매 제품 광고이므로 허위 정보 생성 금지).
    """
    discount_percent: Optional[int] = None
    ends_at: Optional[str] = None  # ISO datetime, optional
    coupon: Optional[str] = None


class PromptRequest(BaseModel):
    # output_format은 문구 생성 조건이 아니므로 PromptRequest에는 넣지 않는다.
    # 네이티브 비율 선택은 GenerationRequest와 model_server /infer 계약이 담당한다.
    product_name: str
    category: Optional[str] = None
    price: Optional[int] = None
    selling_points: list[str] = Field(default_factory=list)
    tone: ToneLiteral
    time_slot: Optional[TimeSlotLiteral] = None
    promotion: Optional[PromotionInfo] = None


class PromptResult(BaseModel):
    image_prompt: str
    headline: str
    subcopy: str
    negative_prompt: Optional[str] = None
