from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.image_presets import OutputFormatLiteral
from app.prompt.schemas import ToneLiteral, TimeSlotLiteral


class ProductCreateResponse(BaseModel):
    product_id: str
    image_url: str


class GenerationRequest(BaseModel):
    product_id: str
    tones: list[ToneLiteral] = Field(
        default_factory=lambda: ["emotional", "modern", "practical", "premium"]
    )  # M2 — 항상 4종 동시 생성이 기본값이지만 명시적으로 받는다
    time_slots: list[TimeSlotLiteral]  # PM 승인: 체크박스 다중 선택
    output_formats: list[OutputFormatLiteral] = Field(
        default_factory=lambda: ["thumbnail", "story_vertical"],
        min_length=1,
        max_length=2,
    )

    @field_validator("output_formats")
    @classmethod
    def output_formats_must_be_unique(
        cls,
        values: list[OutputFormatLiteral],
    ) -> list[OutputFormatLiteral]:
        if len(values) != len(set(values)):
            raise ValueError("output_formats must not contain duplicates")
        return values


class GenerationCreateResponse(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    estimated_seconds: int


class JobStepStatus(BaseModel):
    name: str
    status: Literal["pending", "in_progress", "done"]


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int = 0
    current_step: Optional[str] = None
    completed_count: int = 0
    total_count: int = 0
    estimated_seconds: Optional[int] = None
    error_message: Optional[str] = None


class ToneResult(BaseModel):
    result_id: str  # 쇼츠 생성 등 개별 결과 단위 참조용 (M3/S2와 별개로 추가)
    tone: ToneLiteral
    time_slot: Optional[TimeSlotLiteral] = None
    headline: str
    subcopy: str
    source_image_url: Optional[str] = None
    images: dict[str, str]  # output_format -> url
    video_url: Optional[str] = None  # 러시아워 쇼츠 생성 완료 시 채워짐


class GenerationResultResponse(BaseModel):
    job_id: str
    status: Literal["completed"]
    results: list[ToneResult]


class CopyUpdateRequest(BaseModel):
    headline: str
    subcopy: str
