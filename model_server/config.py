from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class InferenceProfile(str, Enum):
    FAST_COMPOSITE = "fast_composite"
    QUALITY_REGENERATE = "quality_regenerate"


def _parse_bool(name: str, raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _positive_int(name: str, raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_float(name: str, raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True, slots=True)
class InferenceConfig:
    profile: InferenceProfile = InferenceProfile.FAST_COMPOSITE
    image_size: int = 1024
    seed: int = 42
    fast_steps: int = 4
    fast_guidance_scale: float = 1.0
    quality_steps: int = 30
    quality_guidance_scale: float = 7.5
    controlnet_conditioning_scale: float = 0.6
    ip_adapter_scale: float = 0.3
    product_fill_ratio: float = 0.5
    cache_max_entries: int = 16
    cache_ttl_seconds: float = 3600.0
    enable_torch_compile: bool = False
    allow_cpu_inference: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "InferenceConfig":
        defaults = cls()
        profile_raw = environ.get("MODEL_PROFILE", defaults.profile.value)
        try:
            profile = InferenceProfile(profile_raw)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in InferenceProfile)
            raise ValueError(f"MODEL_PROFILE must be one of: {allowed}") from exc

        image_size = _positive_int(
            "IMAGE_SIZE", environ.get("IMAGE_SIZE", str(defaults.image_size))
        )
        if image_size % 8:
            raise ValueError("IMAGE_SIZE must be divisible by 8")

        product_fill_ratio = _positive_float(
            "PRODUCT_FILL_RATIO",
            environ.get("PRODUCT_FILL_RATIO", str(defaults.product_fill_ratio)),
        )
        if product_fill_ratio > 1:
            raise ValueError("PRODUCT_FILL_RATIO must be at most 1")

        return cls(
            profile=profile,
            image_size=image_size,
            seed=int(environ.get("SEED", str(defaults.seed))),
            fast_steps=_positive_int(
                "FAST_NUM_INFERENCE_STEPS",
                environ.get("FAST_NUM_INFERENCE_STEPS", str(defaults.fast_steps)),
            ),
            fast_guidance_scale=_positive_float(
                "FAST_GUIDANCE_SCALE",
                environ.get(
                    "FAST_GUIDANCE_SCALE", str(defaults.fast_guidance_scale)
                ),
            ),
            quality_steps=_positive_int(
                "QUALITY_NUM_INFERENCE_STEPS",
                environ.get(
                    "QUALITY_NUM_INFERENCE_STEPS", str(defaults.quality_steps)
                ),
            ),
            quality_guidance_scale=_positive_float(
                "QUALITY_GUIDANCE_SCALE",
                environ.get(
                    "QUALITY_GUIDANCE_SCALE", str(defaults.quality_guidance_scale)
                ),
            ),
            controlnet_conditioning_scale=_positive_float(
                "CONTROLNET_CONDITIONING_SCALE",
                environ.get(
                    "CONTROLNET_CONDITIONING_SCALE",
                    str(defaults.controlnet_conditioning_scale),
                ),
            ),
            ip_adapter_scale=_positive_float(
                "IP_ADAPTER_SCALE",
                environ.get("IP_ADAPTER_SCALE", str(defaults.ip_adapter_scale)),
            ),
            product_fill_ratio=product_fill_ratio,
            cache_max_entries=_positive_int(
                "PRODUCT_CACHE_MAX_ENTRIES",
                environ.get(
                    "PRODUCT_CACHE_MAX_ENTRIES", str(defaults.cache_max_entries)
                ),
            ),
            cache_ttl_seconds=_positive_float(
                "PRODUCT_CACHE_TTL_SECONDS",
                environ.get(
                    "PRODUCT_CACHE_TTL_SECONDS", str(defaults.cache_ttl_seconds)
                ),
            ),
            enable_torch_compile=_parse_bool(
                "ENABLE_TORCH_COMPILE",
                environ.get(
                    "ENABLE_TORCH_COMPILE", str(defaults.enable_torch_compile)
                ),
            ),
            allow_cpu_inference=_parse_bool(
                "ALLOW_CPU_INFERENCE",
                environ.get(
                    "ALLOW_CPU_INFERENCE", str(defaults.allow_cpu_inference)
                ),
            ),
        )
