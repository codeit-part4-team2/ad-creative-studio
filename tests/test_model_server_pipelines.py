from __future__ import annotations

from dataclasses import replace
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

from model_server.config import InferenceConfig, InferenceProfile
from model_server.pipelines import (
    DiffusersGenerationPipeline,
    LoadedPipeline,
    build_background_prompt,
)
from model_server.preprocessing import ProductArtifacts


class _FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.embedding_calls = 0

    def __call__(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        width = int(kwargs.get("width", 16))
        height = int(kwargs.get("height", 16))
        return SimpleNamespace(images=[Image.new("RGB", (width, height), "green")])

    def prepare_ip_adapter_image_embeds(self, **_: object) -> list[str]:
        self.embedding_calls += 1
        return ["cached-embedding"]


def _artifacts() -> ProductArtifacts:
    return ProductArtifacts(
        product_rgba=Image.new("RGBA", (16, 16), (255, 0, 0, 255)),
        product_on_white=Image.new("RGB", (16, 16), "white"),
        alpha_mask=Image.new("L", (16, 16), 255),
        canny_image=Image.new("RGB", (16, 16), "black"),
    )


def test_background_prompt_requests_an_empty_lower_center_product_area() -> None:
    prompt = build_background_prompt("warm morning cafe, natural light")

    assert "warm morning cafe, natural light" in prompt
    assert "empty product photography scene" in prompt
    assert "clear lower-center placement area" in prompt


def test_fast_pipeline_is_lazy_and_uses_four_step_lcm_parameters() -> None:
    config = replace(
        InferenceConfig(),
        image_size=16,
        fast_background_size=8,
    )
    fake = _FakePipeline()
    loads: list[InferenceProfile] = []
    pipeline = DiffusersGenerationPipeline(
        config,
        loader=lambda cfg: loads.append(cfg.profile) or LoadedPipeline(fake, "cuda"),
        generator_factory=lambda device, seed: (device, seed),
        reset_peak_memory=lambda: None,
        peak_memory_reader=lambda: 3.25,
    )

    assert loads == []
    assert pipeline.is_loaded is False
    result = pipeline.generate(
        cache_key="product:1",
        prompt="warm cafe",
        negative_prompt="blurry",
        artifacts=_artifacts(),
    )

    assert loads == [InferenceProfile.FAST_COMPOSITE]
    assert pipeline.is_loaded is True
    assert result.requires_composite is True
    assert result.peak_vram_gb == 3.25
    assert fake.calls[0]["num_inference_steps"] == 4
    assert fake.calls[0]["guidance_scale"] == 1.0
    assert fake.calls[0]["width"] == 8
    assert fake.calls[0]["height"] == 8
    assert result.image.size == (16, 16)
    assert "image" not in fake.calls[0]
    assert "ip_adapter_image" not in fake.calls[0]


def test_explicit_load_is_idempotent() -> None:
    fake = _FakePipeline()
    load_count = 0

    def loader(_: InferenceConfig) -> LoadedPipeline:
        nonlocal load_count
        load_count += 1
        return LoadedPipeline(fake, "cuda")

    pipeline = DiffusersGenerationPipeline(InferenceConfig(), loader=loader)

    pipeline.load()
    pipeline.load()

    assert pipeline.is_loaded is True
    assert load_count == 1


def test_default_loader_fails_before_diffusers_import_without_cuda(monkeypatch) -> None:
    from model_server.pipelines import _load_diffusers_pipeline

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        float16=object(),
        float32=object(),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.delitem(sys.modules, "diffusers", raising=False)

    with pytest.raises(RuntimeError, match="CUDA GPU is required"):
        _load_diffusers_pipeline(InferenceConfig())


def test_quality_pipeline_reuses_ip_adapter_embedding_for_same_product() -> None:
    config = replace(
        InferenceConfig(),
        profile=InferenceProfile.QUALITY_REGENERATE,
        image_size=16,
    )
    fake = _FakePipeline()
    pipeline = DiffusersGenerationPipeline(
        config,
        loader=lambda _: LoadedPipeline(fake, "cuda"),
        generator_factory=lambda device, seed: (device, seed),
        reset_peak_memory=lambda: None,
        peak_memory_reader=lambda: 4.0,
    )

    for _ in range(2):
        pipeline.generate(
            cache_key="product:1",
            prompt="premium marble",
            negative_prompt="blurry",
            artifacts=_artifacts(),
        )

    assert fake.embedding_calls == 1
    assert len(fake.calls) == 2
    assert fake.calls[0]["num_inference_steps"] == 30
    assert fake.calls[0]["guidance_scale"] == 7.5
    assert fake.calls[0]["width"] == 16
    assert fake.calls[0]["height"] == 16
    assert fake.calls[0]["image"].mode == "RGB"
    assert fake.calls[0]["ip_adapter_image_embeds"] == ["cached-embedding"]
