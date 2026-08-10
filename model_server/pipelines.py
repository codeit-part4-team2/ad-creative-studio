from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

from PIL import Image

from model_server.cache import TTLCache
from model_server.config import InferenceConfig, InferenceProfile
from model_server.preprocessing import ProductArtifacts


@dataclass(frozen=True, slots=True)
class LoadedPipeline:
    pipeline: Any
    device: str


@dataclass(frozen=True, slots=True)
class GenerationResult:
    image: Image.Image
    requires_composite: bool
    peak_vram_gb: float | None


def build_background_prompt(prompt: str) -> str:
    return (
        f"{prompt}, empty product photography scene, "
        "clear lower-center placement area, realistic surface, "
        "commercial advertising background, no foreground product"
    )


def _default_generator_factory(device: str, seed: int) -> object:
    import torch

    return torch.Generator(device=device).manual_seed(seed)


def _reset_peak_memory() -> None:
    import torch

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def _read_peak_memory() -> float | None:
    import torch

    if not torch.cuda.is_available():
        return None
    return torch.cuda.max_memory_allocated() / (1024**3)


def _compile_pipeline(pipeline: Any, torch_module: Any) -> None:
    pipeline.unet.to(memory_format=torch_module.channels_last)
    pipeline.unet = torch_module.compile(
        pipeline.unet,
        mode="reduce-overhead",
        fullgraph=True,
    )
    if hasattr(pipeline, "controlnet"):
        pipeline.controlnet.to(memory_format=torch_module.channels_last)
        pipeline.controlnet = torch_module.compile(
            pipeline.controlnet,
            mode="reduce-overhead",
            fullgraph=True,
        )


def _load_diffusers_pipeline(config: InferenceConfig) -> LoadedPipeline:
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu" and not config.allow_cpu_inference:
        raise RuntimeError(
            "CUDA GPU is required. Set ALLOW_CPU_INFERENCE=true only for explicit development runs."
        )

    from diffusers import (
        AutoencoderKL,
        ControlNetModel,
        LCMScheduler,
        StableDiffusionXLControlNetPipeline,
        StableDiffusionXLPipeline,
    )

    dtype = torch.float16 if device == "cuda" else torch.float32
    base_kwargs: dict[str, object] = {
        "torch_dtype": dtype,
        "use_safetensors": True,
    }
    if device == "cuda":
        base_kwargs["variant"] = "fp16"

    if config.profile is InferenceProfile.FAST_COMPOSITE:
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            **base_kwargs,
        )
        pipeline.scheduler = LCMScheduler.from_config(pipeline.scheduler.config)
        pipeline.load_lora_weights(
            "latent-consistency/lcm-lora-sdxl",
            adapter_name="lcm",
        )
        pipeline.set_adapters(["lcm"], adapter_weights=[1.0])
    else:
        controlnet = ControlNetModel.from_pretrained(
            "diffusers/controlnet-canny-sdxl-1.0",
            torch_dtype=dtype,
            use_safetensors=True,
        )
        vae = AutoencoderKL.from_pretrained(
            "madebyollin/sdxl-vae-fp16-fix",
            torch_dtype=dtype,
            use_safetensors=True,
        )
        pipeline = StableDiffusionXLControlNetPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            controlnet=controlnet,
            vae=vae,
            **base_kwargs,
        )
        pipeline.load_ip_adapter(
            "h94/IP-Adapter",
            subfolder="sdxl_models",
            weight_name="ip-adapter_sdxl.bin",
        )
        pipeline.set_ip_adapter_scale(config.ip_adapter_scale)

    pipeline = pipeline.to(device)
    if config.enable_torch_compile and device == "cuda":
        _compile_pipeline(pipeline, torch)
    return LoadedPipeline(pipeline=pipeline, device=device)


class DiffusersGenerationPipeline:
    def __init__(
        self,
        config: InferenceConfig,
        *,
        loader: Callable[[InferenceConfig], LoadedPipeline] = _load_diffusers_pipeline,
        generator_factory: Callable[[str, int], object] = _default_generator_factory,
        reset_peak_memory: Callable[[], None] = _reset_peak_memory,
        peak_memory_reader: Callable[[], float | None] = _read_peak_memory,
    ) -> None:
        self._config = config
        self._loader = loader
        self._generator_factory = generator_factory
        self._reset_peak_memory = reset_peak_memory
        self._peak_memory_reader = peak_memory_reader
        self._loaded: LoadedPipeline | None = None
        self._load_lock = Lock()
        self._embedding_cache: TTLCache[str, object] = TTLCache(
            max_entries=config.cache_max_entries,
            ttl_seconds=config.cache_ttl_seconds,
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded is not None

    def load(self) -> None:
        self._get_loaded()

    def _get_loaded(self) -> LoadedPipeline:
        if self._loaded is not None:
            return self._loaded
        with self._load_lock:
            if self._loaded is None:
                self._loaded = self._loader(self._config)
            return self._loaded

    def _quality_embedding(
        self,
        *,
        cache_key: str,
        loaded: LoadedPipeline,
        product_image: Image.Image,
    ) -> object:
        embedding, _ = self._embedding_cache.get_or_create(
            cache_key,
            lambda: loaded.pipeline.prepare_ip_adapter_image_embeds(
                ip_adapter_image=product_image,
                ip_adapter_image_embeds=None,
                device=loaded.device,
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
            ),
        )
        return embedding

    def generate(
        self,
        *,
        cache_key: str,
        prompt: str,
        negative_prompt: str,
        artifacts: ProductArtifacts,
    ) -> GenerationResult:
        loaded = self._get_loaded()
        generator = self._generator_factory(loaded.device, self._config.seed)
        self._reset_peak_memory()

        if self._config.profile is InferenceProfile.FAST_COMPOSITE:
            background_negative = ", ".join(
                item
                for item in (
                    negative_prompt.strip(),
                    "foreground product, appliance, cup, package, logo, text, watermark",
                )
                if item
            )
            output = loaded.pipeline(
                prompt=build_background_prompt(prompt),
                negative_prompt=background_negative,
                num_inference_steps=self._config.fast_steps,
                guidance_scale=self._config.fast_guidance_scale,
                width=self._config.fast_background_size,
                height=self._config.fast_background_size,
                generator=generator,
            )
            requires_composite = True
        else:
            if artifacts.canny_image is None:
                raise ValueError("quality profile requires a Canny control image")
            image_embeds = self._quality_embedding(
                cache_key=cache_key,
                loaded=loaded,
                product_image=artifacts.product_on_white,
            )
            output = loaded.pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=artifacts.canny_image,
                ip_adapter_image_embeds=image_embeds,
                num_inference_steps=self._config.quality_steps,
                guidance_scale=self._config.quality_guidance_scale,
                controlnet_conditioning_scale=(
                    self._config.controlnet_conditioning_scale
                ),
                width=self._config.image_size,
                height=self._config.image_size,
                generator=generator,
            )
            requires_composite = False

        image = output.images[0].convert("RGB")
        if (
            self._config.profile is InferenceProfile.FAST_COMPOSITE
            and image.size != (self._config.image_size, self._config.image_size)
        ):
            image = image.resize(
                (self._config.image_size, self._config.image_size),
                Image.Resampling.LANCZOS,
            )
        return GenerationResult(
            image=image,
            requires_composite=requires_composite,
            peak_vram_gb=self._peak_memory_reader(),
        )
