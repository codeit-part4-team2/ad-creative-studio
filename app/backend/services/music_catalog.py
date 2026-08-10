from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


Tone = Literal["emotional", "modern", "practical", "premium"]
SUPPORTED_TONES = {"emotional", "modern", "practical", "premium"}


class MusicTrack(BaseModel):
    key: str = Field(min_length=1)
    file: str = Field(min_length=1)
    tone: Tone
    title: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    license: str = Field(min_length=1)
    commercial_use: bool
    attribution_required: bool
    attribution_text: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bpm: int = Field(ge=40, le=240)
    path: Path | None = None


class MusicManifest(BaseModel):
    tracks: list[MusicTrack]


class MusicCatalog:
    def __init__(self, tracks_by_tone: dict[str, MusicTrack]) -> None:
        self._tracks_by_tone = tracks_by_tone

    @classmethod
    def load(cls, manifest_path: Path, *, asset_root: Path) -> MusicCatalog:
        manifest = MusicManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        resolved_root = asset_root.resolve()
        tracks_by_tone: dict[str, MusicTrack] = {}

        for track in manifest.tracks:
            if not track.commercial_use:
                raise ValueError(f"{track.key}: commercial_use must be true")
            if track.attribution_required and not track.attribution_text.strip():
                raise ValueError(f"{track.key}: attribution_text is required")

            path = (resolved_root / track.file).resolve()
            if not path.is_relative_to(resolved_root):
                raise ValueError(f"{track.key}: music path escapes asset root")
            if not path.is_file():
                raise ValueError(f"{track.key}: music file does not exist")

            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != track.sha256:
                raise ValueError(f"{track.key}: sha256 mismatch")
            if track.tone in tracks_by_tone:
                raise ValueError(
                    f"{track.tone}: exactly one active track is required"
                )
            tracks_by_tone[track.tone] = track.model_copy(
                update={"path": path}
            )

        if set(tracks_by_tone) != SUPPORTED_TONES:
            raise ValueError(
                "each supported tone requires exactly one active track"
            )
        return cls(tracks_by_tone)

    def select_for_tone(self, tone: str) -> MusicTrack:
        try:
            return self._tracks_by_tone[tone]
        except KeyError as exc:
            raise ValueError(f"unsupported music tone: {tone}") from exc
