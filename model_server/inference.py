from __future__ import annotations

import hashlib
import re
import time
import uuid
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Protocol

from PIL import Image

from app.image_presets import OutputFormatLiteral, resolve_runtime_image_preset
from app.prompt.backgrounds import FastScenePurpose, build_fast_background_prompt
from model_server.cache import TTLCache
from model_server.compositing import composite_product
from model_server.config import InferenceConfig, InferenceProfile
from model_server.pipelines import GenerationResult
from model_server.preprocessing import (
    PreparationResult,
    ProductArtifacts,
    derive_product_artifacts,
)
from model_server.timing import StageTimings

LOGGER = logging.getLogger(__name__)


class Preprocessor(Protocol):
    def prepare(self, cache_key: str, image_url: str) -> PreparationResult: ...


class Pipeline(Protocol):
    def load(self) -> None: ...

    def generate(
        self,
        *,
        cache_key: str,
        prompt: str,
        negative_prompt: str,
        artifacts: object,
        background_size: tuple[int, int],
        output_size: tuple[int, int],
    ) -> GenerationResult: ...


class OutputStore(Protocol):
    def save(self, image: Image.Image, *, tone: str) -> str: ...


@dataclass(frozen=True, slots=True)
class InferenceResult:
    status: str
    generated_image_url: str | None
    product_preserved: bool | None
    preservation_method: str | None
    gen_time_sec: float | None
    gpu_queue_wait_sec: float | None = None
    stage_times_sec: Mapping[str, float] = field(default_factory=dict)
    cache_hit: bool | None = None
    model_profile: str | None = None
    num_inference_steps: int | None = None
    background_size: int | None = None
    output_size: int | None = None
    output_format: OutputFormatLiteral | None = None
    background_width: int | None = None
    background_height: int | None = None
    output_width: int | None = None
    output_height: int | None = None
    peak_vram_gb: float | None = None
    error_message: str | None = None


class FileOutputStore:
    def __init__(self, output_dir: Path, *, url_prefix: str) -> None:
        self._output_dir = output_dir
        self._url_prefix = url_prefix.rstrip("/")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, image: Image.Image, *, tone: str) -> str:
        safe_tone = re.sub(r"[^a-zA-Z0-9_-]+", "-", tone).strip("-") or "image"
        filename = f"{safe_tone}_{uuid.uuid4().hex[:12]}.png"
        image.convert("RGB").save(self._output_dir / filename, format="PNG")
        return f"{self._url_prefix}/{filename}"


def _cache_key(product_id: str, product_image_url: str) -> str:
    digest = hashlib.sha256(
        f"{product_id}\0{product_image_url}".encode("utf-8")
    ).hexdigest()
    return digest


def _cuda_synchronize() -> None:
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def _cuda_empty_cache() -> None:
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class InferenceEngine:
    def __init__(
        self,
        *,
        config: InferenceConfig,
        preprocessor: Preprocessor,
        pipeline: Pipeline,
        output_store: OutputStore,
        compositor: Callable[..., Image.Image] = composite_product,
        synchronize: Callable[[], None] = _cuda_synchronize,
        empty_cache: Callable[[], None] = _cuda_empty_cache,
        artifact_cache: TTLCache[
            tuple[str, object, tuple[int, int], float, bool], ProductArtifacts
        ]
        | None = None,
    ) -> None:
        self._config = config
        self._preprocessor = preprocessor
        self._pipeline = pipeline
        self._output_store = output_store
        self._compositor = compositor
        self._synchronize = synchronize
        self._empty_cache = empty_cache
        self._artifact_cache = artifact_cache or TTLCache(
            max_entries=config.artifact_cache_max_entries,
            ttl_seconds=config.artifact_cache_ttl_seconds,
        )
        self._gpu_lock = Lock()

    @property
    def model_loaded(self) -> bool:
        return bool(getattr(self._pipeline, "is_loaded", False))

    def load_model(self) -> None:
        self._pipeline.load()

    def run(
        self,
        *,
        product_id: str,
        product_image_url: str,
        tone: str,
        image_prompt: str,
        negative_prompt: str,
        time_slot: str | None = None,
        output_format: OutputFormatLiteral = "thumbnail",
        scene_purpose: FastScenePurpose = "standard",
    ) -> InferenceResult:
        started_at = time.perf_counter()
        timings = StageTimings(synchronize=self._synchronize)
        cache_key = _cache_key(product_id, product_image_url)
        preset = resolve_runtime_image_preset(
            output_format,
            fast_background_size=self._config.fast_background_size,
            image_size=self._config.image_size,
        )
        effective_prompt = (
            build_fast_background_prompt(
                tone=tone,
                time_slot=time_slot,
                scene_purpose=scene_purpose,
            )
            if self._config.profile is InferenceProfile.FAST_COMPOSITE
            else image_prompt
        )

        with timings.measure("preprocess"):
            preparation = self._preprocessor.prepare(
                cache_key,
                product_image_url,
            )
            include_canny = (
                self._config.profile is InferenceProfile.QUALITY_REGENERATE
            )
            artifacts, _ = self._artifact_cache.get_or_create(
                (
                    cache_key,
                    preparation.artifacts.source_cache_token,
                    preset.composite_size,
                    self._config.product_fill_ratio,
                    include_canny,
                ),
                lambda: derive_product_artifacts(
                    preparation.artifacts,
                    canvas_size=preset.composite_size,
                    fill_ratio=self._config.product_fill_ratio,
                    include_canny=include_canny,
                ),
            )

        queue_started_at = time.perf_counter()
        self._gpu_lock.acquire()
        gpu_queue_wait_sec = round(time.perf_counter() - queue_started_at, 6)
        try:
            with timings.measure("generate"):
                generation = self._pipeline.generate(
                    cache_key=cache_key,
                    prompt=effective_prompt,
                    negative_prompt=negative_prompt,
                    artifacts=artifacts,
                    background_size=preset.background_size,
                    output_size=preset.composite_size,
                )
            try:
                self._empty_cache()
            except Exception:
                LOGGER.exception(
                    "generate 이후 GPU 캐시 정리에 실패했습니다. 생성된 이미지는 정상 처리합니다."
                )
        finally:
            self._gpu_lock.release()

        output = generation.image
        if generation.requires_composite:
            with timings.measure("composite"):
                output = self._compositor(
                    output,
                    artifacts.product_rgba,
                )
            product_preserved: bool | None = True
            preservation_method = "source_alpha_composite"
        else:
            product_preserved = None
            preservation_method = "not_evaluated"

        with timings.measure("save"):
            generated_image_url = self._output_store.save(output, tone=tone)

        steps = (
            self._config.fast_steps
            if self._config.profile is InferenceProfile.FAST_COMPOSITE
            else self._config.quality_steps
        )
        stage_times_sec = {
            "gpu_queue_wait": gpu_queue_wait_sec,
            **timings.as_dict(),
        }
        default_background_size = (
            self._config.fast_background_size
            if self._config.profile is InferenceProfile.FAST_COMPOSITE
            else self._config.image_size
        )
        background_width = (
            generation.background_width
            if generation.background_width is not None
            else generation.background_size or default_background_size
        )
        background_height = (
            generation.background_height
            if generation.background_height is not None
            else generation.background_size or default_background_size
        )
        output_width = (
            generation.output_width
            if generation.output_width is not None
            else generation.output_size or self._config.image_size
        )
        output_height = (
            generation.output_height
            if generation.output_height is not None
            else generation.output_size or self._config.image_size
        )
        return InferenceResult(
            status="done",
            generated_image_url=generated_image_url,
            product_preserved=product_preserved,
            preservation_method=preservation_method,
            gen_time_sec=round(time.perf_counter() - started_at, 6),
            gpu_queue_wait_sec=gpu_queue_wait_sec,
            stage_times_sec=stage_times_sec,
            cache_hit=preparation.cache_hit,
            model_profile=self._config.profile.value,
            num_inference_steps=steps,
            background_size=(
                background_width
                if background_width == background_height
                else None
            ),
            output_size=output_width if output_width == output_height else None,
            output_format=output_format,
            background_width=background_width,
            background_height=background_height,
            output_width=output_width,
            output_height=output_height,
            peak_vram_gb=generation.peak_vram_gb,
        )
