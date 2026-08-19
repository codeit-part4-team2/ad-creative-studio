from __future__ import annotations

from dataclasses import asdict

import pytest

from model_server.config import InferenceConfig, InferenceProfile


def test_default_config_selects_four_step_fast_composite_profile() -> None:
    config = InferenceConfig.from_env({})

    assert config.profile is InferenceProfile.FAST_COMPOSITE
    assert config.fast_steps == 4
    assert config.fast_guidance_scale == 1.0
    assert config.image_size == 1024
    assert config.fast_background_size == 768
    assert config.allow_cpu_inference is False
    assert config.image_allowed_origins == ("http://localhost:8000",)


def test_config_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="MODEL_PROFILE"):
        InferenceConfig.from_env({"MODEL_PROFILE": "instant_magic"})


def test_config_rejects_non_positive_step_count() -> None:
    with pytest.raises(ValueError, match="FAST_NUM_INFERENCE_STEPS"):
        InferenceConfig.from_env({"FAST_NUM_INFERENCE_STEPS": "0"})


def test_config_parses_explicit_fast_background_size() -> None:
    config = InferenceConfig.from_env({"FAST_BACKGROUND_SIZE": "512"})

    assert config.fast_background_size == 512


def test_config_parses_separate_artifact_cache_limits() -> None:
    values = asdict(InferenceConfig.from_env({
        "ARTIFACT_CACHE_MAX_ENTRIES": "3",
        "ARTIFACT_CACHE_TTL_SECONDS": "120",
    }))

    assert values["artifact_cache_max_entries"] == 3
    assert values["artifact_cache_ttl_seconds"] == 120.0


@pytest.mark.parametrize("value", ["0", "770", "1032"])
def test_fast_background_size_must_be_positive_aligned_and_not_larger(
    value: str,
) -> None:
    with pytest.raises(ValueError, match="FAST_BACKGROUND_SIZE"):
        InferenceConfig.from_env({"FAST_BACKGROUND_SIZE": value})


def test_config_parses_explicit_boolean_values() -> None:
    config = InferenceConfig.from_env({
        "ENABLE_TORCH_COMPILE": "true",
        "ENABLE_VAE_TILING": "true",
        "ALLOW_CPU_INFERENCE": "true",
    })

    assert config.enable_torch_compile is True
    assert config.enable_vae_tiling is True
    assert config.allow_cpu_inference is True


def test_vae_tiling_defaults_to_disabled() -> None:
    config = InferenceConfig.from_env({})

    assert config.enable_vae_tiling is False


def test_config_parses_explicit_image_origin_allowlist() -> None:
    config = InferenceConfig.from_env({
        "MODEL_IMAGE_ALLOWED_ORIGINS": (
            "https://backend.example, http://backend.internal:8000/"
        ),
    })

    assert config.image_allowed_origins == (
        "https://backend.example",
        "http://backend.internal:8000",
    )


def test_config_rejects_image_origin_with_path() -> None:
    with pytest.raises(ValueError, match="MODEL_IMAGE_ALLOWED_ORIGINS"):
        InferenceConfig.from_env({
            "MODEL_IMAGE_ALLOWED_ORIGINS": "https://backend.example/files",
        })
