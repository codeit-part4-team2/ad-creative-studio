from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ToneLiteral = Literal["emotional", "practical", "premium", "modern"]
TimeSlotLiteral = Literal[
    "morning",
    "commute_am",
    "afternoon",
    "commute_pm",
    "evening",
    "late_night",
]


class InferRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=200)
    product_image_url: str = Field(min_length=1, max_length=2048)
    tone: ToneLiteral
    image_prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str = Field(default="", max_length=4000)
    time_slot: TimeSlotLiteral


class InferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["done", "failed"]
    generated_image_url: str | None = None
    product_preserved: bool | None = None
    preservation_method: str | None = None
    gen_time_sec: float | None = None
    stage_times_sec: dict[str, float] = Field(default_factory=dict)
    cache_hit: bool | None = None
    model_profile: str | None = None
    num_inference_steps: int | None = None
    peak_vram_gb: float | None = None
    error_message: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    model_loaded: bool
