import hashlib
import json
from pathlib import Path

import pytest

from app.backend.services.music_catalog import MusicCatalog


TONES = ("emotional", "modern", "practical", "premium")


def _track(asset_root: Path, tone: str) -> dict:
    path = asset_root / f"{tone}.mp3"
    path.write_bytes(f"licensed-{tone}".encode())
    return {
        "key": f"{tone}_01",
        "file": path.name,
        "tone": tone,
        "title": f"{tone.title()} 01",
        "source_url": f"https://license.example/{tone}",
        "license": "Commercial test fixture",
        "commercial_use": True,
        "attribution_required": False,
        "attribution_text": "",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bpm": 120,
    }


def _write_manifest(tmp_path: Path, tracks: list[dict]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"tracks": tracks}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_catalog_selects_one_verified_track_for_each_tone(tmp_path):
    tracks = [_track(tmp_path, tone) for tone in TONES]
    manifest = _write_manifest(tmp_path, tracks)

    catalog = MusicCatalog.load(manifest, asset_root=tmp_path)

    selected = catalog.select_for_tone("practical")
    assert selected.key == "practical_01"
    assert selected.path == (tmp_path / "practical.mp3").resolve()


def test_catalog_rejects_noncommercial_track(tmp_path):
    tracks = [_track(tmp_path, tone) for tone in TONES]
    tracks[0]["commercial_use"] = False
    manifest = _write_manifest(tmp_path, tracks)

    with pytest.raises(ValueError, match="commercial_use"):
        MusicCatalog.load(manifest, asset_root=tmp_path)


def test_catalog_rejects_hash_mismatch(tmp_path):
    tracks = [_track(tmp_path, tone) for tone in TONES]
    tracks[0]["sha256"] = "0" * 64
    manifest = _write_manifest(tmp_path, tracks)

    with pytest.raises(ValueError, match="sha256"):
        MusicCatalog.load(manifest, asset_root=tmp_path)


def test_catalog_rejects_path_outside_asset_root(tmp_path):
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    tracks = [_track(asset_root, tone) for tone in TONES]
    outside = tmp_path / "outside.mp3"
    outside.write_bytes(b"outside")
    tracks[0]["file"] = "../outside.mp3"
    tracks[0]["sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    manifest = _write_manifest(tmp_path, tracks)

    with pytest.raises(ValueError, match="asset root"):
        MusicCatalog.load(manifest, asset_root=asset_root)


def test_catalog_requires_attribution_text_when_license_requires_it(tmp_path):
    tracks = [_track(tmp_path, tone) for tone in TONES]
    tracks[0]["attribution_required"] = True
    tracks[0]["attribution_text"] = ""
    manifest = _write_manifest(tmp_path, tracks)

    with pytest.raises(ValueError, match="attribution_text"):
        MusicCatalog.load(manifest, asset_root=tmp_path)


def test_catalog_requires_all_four_tones(tmp_path):
    tracks = [_track(tmp_path, tone) for tone in TONES[:-1]]
    manifest = _write_manifest(tmp_path, tracks)

    with pytest.raises(ValueError, match="each supported tone"):
        MusicCatalog.load(manifest, asset_root=tmp_path)
