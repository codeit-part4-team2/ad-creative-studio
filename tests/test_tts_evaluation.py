import json
import wave
from pathlib import Path

from app.backend.services.tts_provider import TTSAudio
from tools.evaluate_korean_tts import EVALUATION_SENTENCES, run_evaluation


class RecordingProvider:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def synthesize(self, spoken_text: str, output_path: Path) -> TTSAudio:
        self.texts.append(spoken_text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24_000)
            wav_file.writeframes(b"\x00\x00" * 2_400)
        return TTSAudio(
            path=output_path.resolve(),
            duration_sec=0.1,
            sha256="a" * 64,
            engine="fake-melotts",
            voice_preset="deadpan-ai-v1",
        )


def test_evaluation_writes_review_manifest_for_every_sentence(tmp_path):
    provider = RecordingProvider()

    manifest_path = run_evaluation(provider=provider, output_dir=tmp_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert provider.texts == [sentence.text for sentence in EVALUATION_SENTENCES]
    assert manifest["source_revision"] == "209145371cff8fc3bd60d7be902ea69cbdb7965a"
    assert manifest["model_revision"] == "0207e5adfc90129a51b6b03d89be6d84360ed323"
    assert len(manifest["results"]) == len(EVALUATION_SENTENCES)
    assert all(result["pronunciation_status"] == "needs_review" for result in manifest["results"])
    assert all(result["sha256"] == "a" * 64 for result in manifest["results"])
    assert all((tmp_path / result["wav_file"]).is_file() for result in manifest["results"])


def test_evaluation_corpus_covers_required_korean_pronunciation_categories():
    categories = {sentence.category for sentence in EVALUATION_SENTENCES}

    assert {
        "product_name",
        "numbers",
        "time",
        "units",
        "mixed_language",
        "batchim_linking",
    } <= categories
