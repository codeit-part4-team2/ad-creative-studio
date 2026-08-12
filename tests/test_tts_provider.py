import hashlib
import tomllib
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backend.services.tts_provider import (
    MELOTTS_CONFIG_SHA256,
    MELOTTS_KOREAN_MODEL_REVISION,
    MELOTTS_SOURCE_REVISION,
    MELOTTS_CHECKPOINT_SHA256,
    MeloTTSProvider,
)


class FakeMeloEngine:
    def __init__(self, *, sample_rate: int = 24_000) -> None:
        self.hps = SimpleNamespace(
            data=SimpleNamespace(
                sampling_rate=sample_rate,
                spk2id={"KR": 0},
            )
        )
        self.calls: list[dict[str, object]] = []

    def tts_to_file(
        self,
        text: str,
        speaker_id: int,
        output_path: str,
        **kwargs,
    ) -> None:
        self.calls.append(
            {
                "text": text,
                "speaker_id": speaker_id,
                "output_path": output_path,
                **kwargs,
            }
        )
        with wave.open(output_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.hps.data.sampling_rate)
            wav_file.writeframes(b"\x00\x00" * (self.hps.data.sampling_rate // 2))


def test_provider_writes_wav_and_returns_hash(tmp_path):
    engine = FakeMeloEngine()
    provider = MeloTTSProvider(
        output_root=tmp_path,
        engine_factory=lambda: engine,
    )

    audio = provider.synthesize(
        "정확하게 읽습니다.",
        tmp_path / "line.wav",
    )

    assert audio.path == (tmp_path / "line.wav").resolve()
    assert audio.duration_sec == pytest.approx(0.5)
    assert audio.sha256 == hashlib.sha256(audio.path.read_bytes()).hexdigest()
    assert audio.engine == "melotts-korean"
    assert audio.voice_preset == "deadpan-ai-v1"
    assert engine.calls[0]["text"] == "정확하게 읽습니다."
    assert engine.calls[0]["speaker_id"] == 0
    assert engine.calls[0]["speed"] == pytest.approx(0.94)
    assert engine.calls[0]["sdp_ratio"] == pytest.approx(0.2)
    assert engine.calls[0]["noise_scale"] == pytest.approx(0.6)
    assert engine.calls[0]["noise_scale_w"] == pytest.approx(0.8)


def test_provider_loads_engine_only_once(tmp_path):
    engine = FakeMeloEngine()
    load_count = 0

    def load_engine():
        nonlocal load_count
        load_count += 1
        return engine

    provider = MeloTTSProvider(
        output_root=tmp_path,
        engine_factory=load_engine,
    )
    provider.synthesize("첫 문장입니다.", tmp_path / "first.wav")
    provider.synthesize("둘째 문장입니다.", tmp_path / "second.wav")

    assert load_count == 1


def test_runtime_validation_loads_pinned_engine_once_before_synthesis(tmp_path):
    engine = FakeMeloEngine()
    load_count = 0

    def load_engine():
        nonlocal load_count
        load_count += 1
        return engine

    provider = MeloTTSProvider(output_root=tmp_path, engine_factory=load_engine)

    provider.validate_runtime()
    provider.synthesize("환경 확인 문장입니다.", tmp_path / "validated.wav")

    assert load_count == 1
    assert (tmp_path / "validated.wav").is_file()


def test_provider_rejects_empty_text(tmp_path):
    provider = MeloTTSProvider(
        output_root=tmp_path,
        engine_factory=FakeMeloEngine,
    )

    with pytest.raises(ValueError, match="비어"):
        provider.synthesize("   ", tmp_path / "empty.wav")


def test_provider_rejects_output_outside_root(tmp_path):
    root = tmp_path / "audio"
    provider = MeloTTSProvider(
        output_root=root,
        engine_factory=FakeMeloEngine,
    )

    with pytest.raises(ValueError, match="출력 경로"):
        provider.synthesize("문장입니다.", tmp_path / "escape.wav")


def test_provider_requires_explicit_model_files_without_fake_engine(tmp_path):
    provider = MeloTTSProvider(output_root=tmp_path)

    with pytest.raises(RuntimeError, match="MELOTTS_CONFIG_PATH"):
        provider.synthesize("문장입니다.", tmp_path / "line.wav")


def test_provider_rejects_changed_official_model_before_import(tmp_path):
    config_path = tmp_path / "config.json"
    checkpoint_path = tmp_path / "checkpoint.pth"
    config_path.write_text("{}", encoding="utf-8")
    checkpoint_path.write_bytes(b"not-the-approved-checkpoint")
    provider = MeloTTSProvider(
        output_root=tmp_path / "audio",
        config_path=config_path,
        checkpoint_path=checkpoint_path,
    )

    with pytest.raises(RuntimeError, match="SHA-256"):
        provider.synthesize("문장입니다.", tmp_path / "audio" / "line.wav")


def test_official_melotts_revisions_and_hashes_are_exactly_pinned():
    assert MELOTTS_SOURCE_REVISION == "209145371cff8fc3bd60d7be902ea69cbdb7965a"
    assert MELOTTS_KOREAN_MODEL_REVISION == "0207e5adfc90129a51b6b03d89be6d84360ed323"
    assert MELOTTS_CONFIG_SHA256 == "74543376976dfadde45ba34336fa79c7e95509f43a7c2e701b22c0f71fd7695c"
    assert MELOTTS_CHECKPOINT_SHA256 == "48e3ff3fd0b5348e095f0468e60ae727507564100f58142ef3a922ead6e0a4d0"


def test_python312_tts_runtime_dependencies_are_pinned():
    project_root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = set(project["project"]["optional-dependencies"]["tts"])

    assert {
        "torch==2.5.1",
        "torchaudio==2.5.1",
        "transformers==4.41.2",
        "librosa==0.10.2.post1",
        "numpy==1.26.4",
        "setuptools==80.9.0",
    } <= dependencies
