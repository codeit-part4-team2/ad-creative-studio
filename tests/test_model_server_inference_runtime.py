from __future__ import annotations

import threading
import time
from dataclasses import replace
from pathlib import Path

from PIL import Image

from model_server.config import InferenceConfig, InferenceProfile
from model_server.inference import FileOutputStore, InferenceEngine
from model_server.pipelines import GenerationResult
from model_server.preprocessing import (
    PreparationResult,
    ProductArtifacts,
)


def _artifacts() -> ProductArtifacts:
    product = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    product.putpixel((8, 8), (220, 10, 20, 255))
    return ProductArtifacts(
        product_rgba=product,
        product_on_white=Image.new("RGB", (16, 16), "white"),
        alpha_mask=product.getchannel("A"),
        canny_image=Image.new("RGB", (16, 16), "black"),
    )


class _FakePreprocessor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def prepare(self, cache_key: str, image_url: str) -> PreparationResult:
        self.calls.append((cache_key, image_url))
        return PreparationResult(artifacts=_artifacts(), cache_hit=True)


class _FakePipeline:
    def __init__(self, *, requires_composite: bool = True) -> None:
        self.requires_composite = requires_composite
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> GenerationResult:
        self.calls.append(kwargs)
        return GenerationResult(
            image=Image.new("RGB", (16, 16), (0, 128, 0)),
            requires_composite=self.requires_composite,
            peak_vram_gb=3.5,
        )


class _CaptureStore:
    def __init__(self) -> None:
        self.saved: list[Image.Image] = []

    def save(self, image: Image.Image, *, tone: str) -> str:
        self.saved.append(image.copy())
        return f"/files/outputs/{tone}.png"


def test_fast_inference_composites_source_and_returns_stage_metadata() -> None:
    config = replace(
        InferenceConfig(),
        image_size=16,
        fast_background_size=8,
    )
    preprocessor = _FakePreprocessor()
    pipeline = _FakePipeline()
    store = _CaptureStore()
    engine = InferenceEngine(
        config=config,
        preprocessor=preprocessor,
        pipeline=pipeline,
        output_store=store,
        synchronize=lambda: None,
    )

    result = engine.run(
        product_id="p-1",
        product_image_url="https://images.example/product.png",
        tone="premium",
        image_prompt="premium marble studio",
        negative_prompt="blurry",
    )

    assert result.status == "done"
    assert result.generated_image_url == "/files/outputs/premium.png"
    assert result.product_preserved is True
    assert result.preservation_method == "source_alpha_composite"
    assert result.cache_hit is True
    assert result.model_profile == "fast_composite"
    assert result.num_inference_steps == 4
    assert result.background_size == 8
    assert result.output_size == 16
    assert result.peak_vram_gb == 3.5
    assert result.gpu_queue_wait_sec is not None
    assert result.gpu_queue_wait_sec >= 0.0
    assert set(result.stage_times_sec) == {
        "preprocess",
        "gpu_queue_wait",
        "generate",
        "composite",
        "save",
    }
    assert result.stage_times_sec["gpu_queue_wait"] == result.gpu_queue_wait_sec
    assert store.saved[0].getpixel((8, 8)) == (220, 10, 20)
    assert store.saved[0].getpixel((0, 0)) == (0, 128, 0)


def test_quality_result_does_not_claim_unmeasured_product_preservation() -> None:
    config = replace(
        InferenceConfig(),
        profile=InferenceProfile.QUALITY_REGENERATE,
        image_size=16,
        fast_background_size=8,
    )
    pipeline = _FakePipeline(requires_composite=False)
    engine = InferenceEngine(
        config=config,
        preprocessor=_FakePreprocessor(),
        pipeline=pipeline,
        output_store=_CaptureStore(),
        synchronize=lambda: None,
    )

    result = engine.run(
        product_id="p-1",
        product_image_url="https://images.example/product.png",
        tone="modern",
        image_prompt="modern pop art",
        negative_prompt="blurry",
    )

    assert result.product_preserved is None
    assert result.preservation_method == "not_evaluated"
    assert result.background_size == 16
    assert result.output_size == 16


def test_inference_engine_serializes_pipeline_generation() -> None:
    entered = threading.Event()
    second_preprocessed = threading.Event()
    release = threading.Event()
    call_count = 0
    call_count_lock = threading.Lock()

    class SignalingPreprocessor(_FakePreprocessor):
        def prepare(self, cache_key: str, image_url: str) -> PreparationResult:
            result = super().prepare(cache_key, image_url)
            if len(self.calls) == 2:
                second_preprocessed.set()
            return result

    class BlockingPipeline:
        def generate(self, **_: object) -> GenerationResult:
            nonlocal call_count
            with call_count_lock:
                call_count += 1
            entered.set()
            release.wait(timeout=2)
            return GenerationResult(
                image=Image.new("RGB", (16, 16), "green"),
                requires_composite=True,
                peak_vram_gb=1.0,
            )

    engine = InferenceEngine(
        config=replace(InferenceConfig(), image_size=16),
        preprocessor=SignalingPreprocessor(),
        pipeline=BlockingPipeline(),
        output_store=_CaptureStore(),
        synchronize=lambda: None,
    )

    def run(product_id: str) -> None:
        engine.run(
            product_id=product_id,
            product_image_url="https://images.example/product.png",
            tone="practical",
            image_prompt="clean studio",
            negative_prompt="",
        )

    first = threading.Thread(target=run, args=("p-1",))
    second = threading.Thread(target=run, args=("p-2",))
    first.start()
    assert entered.wait(timeout=1)
    second.start()
    assert second_preprocessed.wait(timeout=1)
    assert call_count == 1
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert call_count == 2
    assert not first.is_alive()
    assert not second.is_alive()


def test_inference_engine_reports_gpu_queue_wait_separately() -> None:
    prepared = threading.Event()
    results: list[object] = []

    class SignalingPreprocessor(_FakePreprocessor):
        def prepare(self, cache_key: str, image_url: str) -> PreparationResult:
            result = super().prepare(cache_key, image_url)
            prepared.set()
            return result

    engine = InferenceEngine(
        config=replace(InferenceConfig(), image_size=16),
        preprocessor=SignalingPreprocessor(),
        pipeline=_FakePipeline(),
        output_store=_CaptureStore(),
        synchronize=lambda: None,
    )
    engine._gpu_lock.acquire()

    request = threading.Thread(
        target=lambda: results.append(
            engine.run(
                product_id="p-queued",
                product_image_url="https://images.example/product.png",
                tone="premium",
                image_prompt="premium studio",
                negative_prompt="",
            )
        )
    )
    request.start()
    assert prepared.wait(timeout=1)
    time.sleep(0.06)
    engine._gpu_lock.release()
    request.join(timeout=2)

    assert not request.is_alive()
    assert len(results) == 1
    result = results[0]
    assert result.gpu_queue_wait_sec is not None
    assert result.gpu_queue_wait_sec >= 0.04
    assert result.stage_times_sec["gpu_queue_wait"] == result.gpu_queue_wait_sec


def test_inference_engine_releases_gpu_lock_after_generation_failure() -> None:
    class FailsOncePipeline(_FakePipeline):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def generate(self, **kwargs: object) -> GenerationResult:
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("generation failed")
            return super().generate(**kwargs)

    engine = InferenceEngine(
        config=replace(InferenceConfig(), image_size=16),
        preprocessor=_FakePreprocessor(),
        pipeline=FailsOncePipeline(),
        output_store=_CaptureStore(),
        synchronize=lambda: None,
    )

    try:
        engine.run(
            product_id="p-failing",
            product_image_url="https://images.example/product.png",
            tone="premium",
            image_prompt="premium studio",
            negative_prompt="",
        )
    except RuntimeError as exc:
        assert str(exc) == "generation failed"
    else:
        raise AssertionError("first generation must fail")

    result = engine.run(
        product_id="p-retry",
        product_image_url="https://images.example/product.png",
        tone="premium",
        image_prompt="premium studio",
        negative_prompt="",
    )

    assert result.status == "done"
    assert result.gpu_queue_wait_sec is not None


def test_cache_cleanup_failure_does_not_discard_generated_result() -> None:
    def failing_empty_cache() -> None:
        raise RuntimeError("cuda cache cleanup exploded")

    engine = InferenceEngine(
        config=replace(InferenceConfig(), image_size=16),
        preprocessor=_FakePreprocessor(),
        pipeline=_FakePipeline(),
        output_store=_CaptureStore(),
        synchronize=lambda: None,
        empty_cache=failing_empty_cache,
    )

    result = engine.run(
        product_id="p-cache-fail",
        product_image_url="https://images.example/product.png",
        tone="premium",
        image_prompt="premium studio",
        negative_prompt="",
    )

    assert result.status == "done"
    assert result.generated_image_url is not None
    assert not engine._gpu_lock.locked()


def test_file_output_store_creates_png_and_public_url(tmp_path: Path) -> None:
    store = FileOutputStore(tmp_path, url_prefix="/files/outputs")

    url = store.save(Image.new("RGB", (4, 4), "red"), tone="premium")

    assert url.startswith("/files/outputs/premium_")
    assert url.endswith(".png")
    saved_files = list(tmp_path.glob("premium_*.png"))
    assert len(saved_files) == 1
    with Image.open(saved_files[0]) as saved:
        assert saved.getpixel((0, 0)) == (255, 0, 0)
