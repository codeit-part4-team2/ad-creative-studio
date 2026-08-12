from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from app.backend.services.tts_provider import (
    MELOTTS_KOREAN_MODEL_REVISION,
    MELOTTS_SOURCE_REVISION,
    MeloTTSProvider,
    TTSProvider,
)


@dataclass(frozen=True, slots=True)
class EvaluationSentence:
    key: str
    category: str
    text: str


EVALUATION_SENTENCES: tuple[EvaluationSentence, ...] = (
    EvaluationSentence("product_microwave", "product_name", "테스트 전자레인지입니다."),
    EvaluationSentence("numbers_price", "numbers", "가격은 십이만 삼천사백 원입니다."),
    EvaluationSentence("commute_time", "time", "오전 여덟 시 삼십 분입니다."),
    EvaluationSentence("capacity_unit", "units", "용량은 삼백오십 밀리리터입니다."),
    EvaluationSentence("mixed_usb_c", "mixed_language", "유에스비 씨 충전을 지원합니다."),
    EvaluationSentence("batchim_linking", "batchim_linking", "밥을 먹고 출근합니다."),
    EvaluationSentence("self_aware", "product_name", "저는 퇴근을 하지 않습니다."),
)


def run_evaluation(*, provider: TTSProvider, output_dir: Path) -> Path:
    resolved_output = output_dir.expanduser().resolve()
    resolved_output.mkdir(parents=True, exist_ok=True)
    provider.validate_runtime()
    results: list[dict[str, object]] = []
    for sentence in EVALUATION_SENTENCES:
        wav_path = resolved_output / f"{sentence.key}.wav"
        audio = provider.synthesize(sentence.text, wav_path)
        results.append(
            {
                **asdict(sentence),
                "wav_file": audio.path.relative_to(resolved_output).as_posix(),
                "duration_sec": round(audio.duration_sec, 6),
                "sha256": audio.sha256,
                "engine": audio.engine,
                "voice_preset": audio.voice_preset,
                "pronunciation_status": "needs_review",
                "review_notes": "",
            }
        )

    manifest = {
        "source_revision": MELOTTS_SOURCE_REVISION,
        "model_revision": MELOTTS_KOREAN_MODEL_REVISION,
        "results": results,
    }
    manifest_path = resolved_output / "results.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="고정 문장으로 MeloTTS 한국어 발음을 평가합니다.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    provider = MeloTTSProvider(
        output_root=args.output_dir,
        config_path=args.config,
        checkpoint_path=args.checkpoint,
    )
    manifest_path = run_evaluation(provider=provider, output_dir=args.output_dir)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
