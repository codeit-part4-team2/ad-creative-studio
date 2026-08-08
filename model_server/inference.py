from __future__ import annotations

import hashlib
import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Protocol

from PIL import Image

from model_server.compositing import composite_product
from model_server.config import InferenceConfig, InferenceProfile
from model_server.pipelines import GenerationResult
from model_server.preprocessing import PreparationResult
from model_server.timing import StageTimings


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
    stage_times_sec: Mapping[str, float] = field(default_factory=dict)
    cache_hit: bool | None = None
    model_profile: str | None = None
    num_inference_steps: int | None = None
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
    ) -> None:
        self._config = config
        self._preprocessor = preprocessor
        self._pipeline = pipeline
        self._output_store = output_store
        self._compositor = compositor
        self._synchronize = synchronize
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
    ) -> InferenceResult:
        started_at = time.perf_counter()
        timings = StageTimings(synchronize=self._synchronize)
        cache_key = _cache_key(product_id, product_image_url)

        with timings.measure("preprocess"):
            preparation = self._preprocessor.prepare(
                cache_key,
                product_image_url,
            )

        with self._gpu_lock:
            with timings.measure("generate"):
                generation = self._pipeline.generate(
                    cache_key=cache_key,
                    prompt=image_prompt,
                    negative_prompt=negative_prompt,
                    artifacts=preparation.artifacts,
                )

        output = generation.image
        if generation.requires_composite:
            with timings.measure("composite"):
                output = self._compositor(
                    output,
                    preparation.artifacts.product_rgba,
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
        return InferenceResult(
            status="done",
            generated_image_url=generated_image_url,
            product_preserved=product_preserved,
            preservation_method=preservation_method,
            gen_time_sec=round(time.perf_counter() - started_at, 6),
            stage_times_sec=timings.as_dict(),
            cache_hit=preparation.cache_hit,
            model_profile=self._config.profile.value,
            num_inference_steps=steps,
            peak_vram_gb=generation.peak_vram_gb,
        )
