from __future__ import annotations

import pytest

from model_server.config import InferenceConfig, InferenceProfile


def test_default_config_selects_four_step_fast_composite_profile() -> None:
    config = InferenceConfig.from_env({})

    assert config.profile is InferenceProfile.FAST_COMPOSITE
    assert config.fast_steps == 4
    assert config.fast_guidance_scale == 1.0
    assert config.image_size == 1024
    assert config.allow_cpu_inference is False


def test_config_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="MODEL_PROFILE"):
        InferenceConfig.from_env({"MODEL_PROFILE": "instant_magic"})


def test_config_rejects_non_positive_step_count() -> None:
    with pytest.raises(ValueError, match="FAST_NUM_INFERENCE_STEPS"):
        InferenceConfig.from_env({"FAST_NUM_INFERENCE_STEPS": "0"})


def test_config_parses_explicit_boolean_values() -> None:
    config = InferenceConfig.from_env({
        "ENABLE_TORCH_COMPILE": "true",
        "ALLOW_CPU_INFERENCE": "true",
    })

    assert config.enable_torch_compile is True
    assert config.allow_cpu_inference is True
