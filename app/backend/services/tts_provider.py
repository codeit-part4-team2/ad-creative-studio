from __future__ import annotations

import hashlib
import os
import sys
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol


MELOTTS_SOURCE_REVISION = "209145371cff8fc3bd60d7be902ea69cbdb7965a"
MELOTTS_KOREAN_MODEL_REVISION = "0207e5adfc90129a51b6b03d89be6d84360ed323"
MELOTTS_CONFIG_SHA256 = "74543376976dfadde45ba34336fa79c7e95509f43a7c2e701b22c0f71fd7695c"
MELOTTS_CHECKPOINT_SHA256 = "48e3ff3fd0b5348e095f0468e60ae727507564100f58142ef3a922ead6e0a4d0"


@dataclass(frozen=True, slots=True)
class DeadpanVoicePreset:
    key: str = "deadpan-ai-v1"
    speed: float = 0.94
    sdp_ratio: float = 0.2
    noise_scale: float = 0.6
    noise_scale_w: float = 0.8


@dataclass(frozen=True, slots=True)
class TTSAudio:
    path: Path
    duration_sec: float
    sha256: str
    engine: str
    voice_preset: str


class TTSProvider(Protocol):
    def synthesize(self, spoken_text: str, output_path: Path) -> TTSAudio: ...


def _wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
    except (EOFError, wave.Error) as exc:
        raise RuntimeError("TTS가 유효한 WAV 파일을 만들지 못했습니다") from exc
    if sample_rate <= 0 or frame_count <= 0:
        raise RuntimeError("TTS WAV에 재생 가능한 오디오가 없습니다")
    return frame_count / sample_rate


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MeloTTSProvider:
    def __init__(
        self,
        *,
        output_root: Path,
        config_path: Path | None = None,
        checkpoint_path: Path | None = None,
        source_dir: Path | None = None,
        engine_factory: Callable[[], Any] | None = None,
        preset: DeadpanVoicePreset = DeadpanVoicePreset(),
    ) -> None:
        self._output_root = output_root.expanduser().resolve()
        self._output_root.mkdir(parents=True, exist_ok=True)
        self._config_path = config_path
        self._checkpoint_path = checkpoint_path
        self._source_dir = source_dir
        self._engine_factory = engine_factory
        self._preset = preset
        self._engine: Any | None = None
        self._load_lock = Lock()
        self._synthesis_lock = Lock()

    def _explicit_model_path(
        self,
        value: Path | None,
        env_name: str,
        expected_sha256: str,
    ) -> Path:
        raw_value = str(value) if value is not None else os.getenv(env_name, "")
        if not raw_value.strip():
            raise RuntimeError(f"{env_name}에 고정된 로컬 모델 경로가 필요합니다")
        resolved = Path(raw_value).expanduser().resolve()
        if not resolved.is_file():
            raise RuntimeError(f"{env_name} 파일을 찾을 수 없습니다")
        actual_sha256 = _file_sha256(resolved)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"{env_name} SHA-256 불일치: 승인된 MeloTTS 파일이 아닙니다"
            )
        return resolved

    def _configure_source_path(self) -> None:
        raw_value = str(self._source_dir) if self._source_dir is not None else os.getenv("MELOTTS_SOURCE_DIR", "")
        if not raw_value.strip():
            return
        source_dir = Path(raw_value).expanduser().resolve()
        if not (source_dir / "melo" / "api.py").is_file():
            raise RuntimeError("MELOTTS_SOURCE_DIR에서 melo/api.py를 찾을 수 없습니다")
        source_text = str(source_dir)
        if source_text not in sys.path:
            sys.path.insert(0, source_text)

    def _load_default_engine(self) -> Any:
        config_path = self._explicit_model_path(
            self._config_path,
            "MELOTTS_CONFIG_PATH",
            MELOTTS_CONFIG_SHA256,
        )
        checkpoint_path = self._explicit_model_path(
            self._checkpoint_path,
            "MELOTTS_CHECKPOINT_PATH",
            MELOTTS_CHECKPOINT_SHA256,
        )
        self._configure_source_path()
        try:
            from melo.api import TTS
        except ImportError as exc:
            raise RuntimeError("고정 버전 MeloTTS 런타임이 설치되지 않았습니다") from exc
        return TTS(
            language="KR",
            device="cpu",
            use_hf=False,
            config_path=str(config_path),
            ckpt_path=str(checkpoint_path),
        )

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        with self._load_lock:
            if self._engine is None:
                factory = self._engine_factory or self._load_default_engine
                self._engine = factory()
        return self._engine

    @staticmethod
    def _speaker_id(engine: Any) -> int:
        speakers = engine.hps.data.spk2id
        if isinstance(speakers, Mapping):
            if "KR" in speakers:
                return int(speakers["KR"])
            if len(speakers) == 1:
                return int(next(iter(speakers.values())))
        if hasattr(speakers, "KR"):
            return int(speakers.KR)
        raise RuntimeError("MeloTTS 한국어 화자 ID를 찾을 수 없습니다")

    def _resolve_output(self, output_path: Path) -> Path:
        resolved = output_path.expanduser().resolve()
        if not resolved.is_relative_to(self._output_root):
            raise ValueError("TTS 출력 경로가 허용된 루트 밖에 있습니다")
        if resolved.suffix.lower() != ".wav":
            raise ValueError("TTS 출력 경로는 WAV 파일이어야 합니다")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def synthesize(self, spoken_text: str, output_path: Path) -> TTSAudio:
        normalized_text = str(spoken_text).strip()
        if not normalized_text:
            raise ValueError("TTS 발화 문장은 비어 있을 수 없습니다")
        resolved_output = self._resolve_output(output_path)
        engine = self._get_engine()
        with self._synthesis_lock:
            engine.tts_to_file(
                normalized_text,
                self._speaker_id(engine),
                str(resolved_output),
                sdp_ratio=self._preset.sdp_ratio,
                noise_scale=self._preset.noise_scale,
                noise_scale_w=self._preset.noise_scale_w,
                speed=self._preset.speed,
                quiet=True,
            )
        duration_sec = _wav_duration(resolved_output)
        return TTSAudio(
            path=resolved_output,
            duration_sec=duration_sec,
            sha256=hashlib.sha256(resolved_output.read_bytes()).hexdigest(),
            engine="melotts-korean",
            voice_preset=self._preset.key,
        )
