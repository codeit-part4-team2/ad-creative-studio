# Rush-Hour Shorts and YouTube Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Generate music-and-caption product Shorts from approved rush-hour ad results, expose approved videos inside the service, and optionally schedule them on one team YouTube test channel.

**Architecture:** Keep the feature inside the existing FastAPI modular monolith. Build deterministic storyboards from stored product facts, render 9:16 MP4 files on the CPU backend, persist independent render/approval/publish states, and hide YouTube behind an injected publisher interface so CI never performs an external upload.

**Tech Stack:** Python 3.12 CI, FastAPI, Pydantic 2, Pillow 12.2.0, FFmpeg/ffprobe, Streamlit, google-api-python-client 2.198.0, pytest.

## Global Constraints

- Work in a feature branch created from the latest main after model optimization PR #15 is L4-verified and merged.
- Until the user lifts the current hold, do not push, open a PR, merge, or execute the commit checkpoint commands shown in this plan.
- Only commute_am and commute_pm results may create Shorts.
- Videos are 1080x1920, 30fps, H.264/AAC, and 10-15 seconds long.
- Do not add TTS, narration, Gemini script generation, or AI music generation.
- Copy may use only stored product name, headline, subcopy, and registered selling points.
- Do not invent discounts, coupons, efficacy claims, promotion deadlines, or prices.
- Approval is required before internal exposure or YouTube upload.
- commute_am activation is 08:00 <= KST < 09:30; commute_pm is 18:00 <= KST < 19:30.
- activation_at must include an offset and be at least 10 minutes in the future.
- YouTube failures must not remove internal approval or exposure eligibility.
- Store state under var/store.json; never put credentials, tokens, or state under the statically served data directory.
- Store rendered MP4 files under data/videos and keep generated media ignored by Git.
- Music assets must have explicit cross-platform commercial-use evidence; do not commit unverified audio.
- Use exact versions for every newly introduced direct dependency.
- Follow existing single-worker assumptions; do not add Redis, Celery, or a separate microservice.
- Every behavior change starts with a failing focused test, then the minimal implementation, then focused and full regression tests.

## File Map

### New production files

- app/backend/schemas/video.py: API enums, job model, request and response schemas.
- app/backend/services/storyboard.py: result lookup, safe image resolution, factual scene building, and source fingerprints.
- app/backend/services/music_catalog.py: manifest parsing, license validation, hash validation, and tone selection.
- app/backend/services/video_renderer.py: Pillow frames, direct FFmpeg composition/audio muxing, ffprobe verification, and MP4 hashing.
- app/backend/services/youtube_publisher.py: publisher protocol, disabled/fake-safe boundary, OAuth credential loading, and YouTube upload.
- app/backend/services/video_workflow.py: job creation, background rendering, approval, rejection, publish orchestration, and state locks.
- app/backend/api/youtube.py: safe YouTube connection-status endpoint.
- scripts/authorize_youtube.py: one-time operator OAuth bootstrap for the team test channel.
- assets/music/README.md: approved music intake and manifest rules.
- assets/music/manifest.example.json: non-secret schema example without unverified audio.

### Existing production files to modify

- app/backend/services/store.py: persist VIDEO_JOBS and recover interrupted work safely.
- app/backend/services/video_generation_service.py: retain compatibility helpers but delegate real work to the new workflow.
- app/backend/api/videos.py: expose create, status, approve, and reject endpoints.
- app/backend/services/exposure.py: attach the latest eligible approved rush-hour video.
- app/backend/api/exposure.py: pass persisted video jobs to exposure selection.
- app/frontend/pages/3_History.py: render progress, preview, warnings, approval/rejection, and schedule controls.
- app/backend/main.py: wire the workflow/publisher during application startup.
- .env.example: document video, music, FFmpeg, and YouTube configuration.
- .gitignore: keep real music files and OAuth material out of source control while retaining README/example manifest.
- pyproject.toml: add an exact-pinned video optional dependency group.
- requirements.txt: install the exact-pinned runtime packages used by CI.
- .github/workflows/test.yml: verify FFmpeg availability and run the renderer integration test.
- docs/api_contract.md: replace the Mock-only video contract with the approved workflow.
- docs/integration_checklist.md: add real renderer, approval, internal exposure, and YouTube manual gates.
- SETUP.md: add FFmpeg and OAuth bootstrap instructions.

### New tests

- tests/test_video_store.py
- tests/test_storyboard.py
- tests/test_music_catalog.py
- tests/test_video_renderer.py
- tests/test_youtube_publisher.py
- tests/test_video_workflow.py
- tests/test_video_api.py

### Existing tests to modify

- tests/test_api.py: isolate VIDEO_JOBS and remove obsolete Mock-only assertions.
- tests/test_exposure.py: cover approved video selection and slot/date filtering.
- tests/test_video_generation.py: retain compatibility-helper tests and remove empty-MP4 behavior.

---

### Task 1: Persist Explicit Video Workflow State

**Files:**
- Create: app/backend/schemas/video.py
- Create: tests/test_video_store.py
- Modify: app/backend/services/store.py
- Modify: tests/test_api.py

**Interfaces:**
- Produces: RenderStatus, ApprovalStatus, PublishStatus, VideoJob, VideoApprovalRequest, VideoStatusResponse.
- Produces: store.VIDEO_JOBS as dict[str, dict].
- Consumed by: Tasks 5-9.

- [ ] **Step 1: Write failing persistence and restart-recovery tests**

~~~python
from app.backend.services import store


def test_video_jobs_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.VIDEO_JOBS["video_1"] = {
        "video_job_id": "video_1",
        "result_id": "res_1",
        "product_id": "prd_1",
        "tone": "practical",
        "time_slot": "commute_am",
        "render_status": "completed",
        "approval_status": "approved",
        "publish_status": "scheduled",
        "video_url": "/files/videos/video_1.mp4",
    }
    store.save()
    store.VIDEO_JOBS.clear()
    store.load()
    assert store.VIDEO_JOBS["video_1"]["publish_status"] == "scheduled"


def test_interrupted_video_jobs_require_review_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_PATH", tmp_path / "store.json")
    store.VIDEO_JOBS.update({
        "rendering": {
            "video_job_id": "rendering",
            "render_status": "processing",
            "approval_status": "pending",
            "publish_status": "not_requested",
        },
        "uploading": {
            "video_job_id": "uploading",
            "render_status": "completed",
            "approval_status": "approved",
            "publish_status": "pending",
            "youtube_video_id": None,
        },
    })
    store.save()
    store.VIDEO_JOBS.clear()
    store.load()
    assert store.VIDEO_JOBS["rendering"]["render_status"] == "failed"
    assert store.VIDEO_JOBS["uploading"]["publish_status"] == "needs_review"
~~~

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

~~~powershell
python -m pytest tests/test_video_store.py -q
~~~

Expected: collection or assertion failure because VIDEO_JOBS and the new video schemas do not exist.

- [ ] **Step 3: Add enums, persisted job fields, and API schemas**

Create app/backend/schemas/video.py with these exact public types:

~~~python
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class RenderStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublishStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    FAILED = "failed"
    AUTH_REQUIRED = "auth_required"
    NEEDS_REVIEW = "needs_review"
    SCHEDULE_EXPIRED = "schedule_expired"


class VideoJob(BaseModel):
    video_job_id: str
    result_id: str
    product_id: str
    tone: Literal["emotional", "modern", "practical", "premium"]
    time_slot: Literal["commute_am", "commute_pm"]
    render_status: RenderStatus = RenderStatus.QUEUED
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    publish_status: PublishStatus = PublishStatus.NOT_REQUESTED
    video_url: str | None = None
    video_sha256: str | None = None
    source_fingerprint: str
    music_key: str | None = None
    music_warning: str | None = None
    silent_publish_confirmed: bool = False
    activation_at: datetime | None = None
    approved_at: datetime | None = None
    youtube_video_id: str | None = None
    youtube_error: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class VideoCreateRequest(BaseModel):
    result_id: str = Field(min_length=1, max_length=200)


class VideoCreateResponse(BaseModel):
    video_job_id: str
    render_status: RenderStatus


class VideoApprovalRequest(BaseModel):
    activation_at: datetime
    publish_to_youtube: bool = True
    allow_silent: bool = False


class VideoStatusResponse(VideoJob):
    pass
~~~

- [ ] **Step 4: Persist VIDEO_JOBS and recover interrupted jobs**

Modify store.py so save, load, and reset_for_tests include video_jobs. On load:

~~~python
VIDEO_JOBS: dict[str, dict] = {}


def _recover_video_jobs() -> None:
    for job in VIDEO_JOBS.values():
        if job.get("render_status") in {"queued", "processing"}:
            job["render_status"] = "failed"
            job["error_message"] = "서버 재시작으로 영상 생성이 중단되었습니다. 다시 시도해주세요."
        if job.get("publish_status") == "pending" and not job.get("youtube_video_id"):
            job["publish_status"] = "needs_review"
            job["youtube_error"] = "게시 성공 여부를 확인한 뒤 다시 시도해주세요."
~~~

Use VideoJob.model_validate in tests to ensure serialized job dictionaries remain schema-valid. Every VIDEO_JOBS mutation stores job.model_dump(mode="json") so datetime and Enum fields remain JSON-serializable.

- [ ] **Step 5: Run focused and store regression tests**

Run:

~~~powershell
python -m pytest tests/test_video_store.py tests/test_store_persistence.py tests/test_api.py -q
~~~

Expected: PASS.

- [ ] **Step 6: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/backend/schemas/video.py app/backend/services/store.py tests/test_video_store.py tests/test_api.py
git commit -m "feat: persist video workflow state"
~~~

Do not execute this checkpoint, push, or open a PR while the user hold remains active.

---

### Task 2: Build Factual Storyboards and Source Fingerprints

**Files:**
- Create: app/backend/services/storyboard.py
- Create: tests/test_storyboard.py
- Modify: app/backend/services/video_generation_service.py
- Modify: tests/test_video_generation.py

**Interfaces:**
- Consumes: store.PRODUCTS and store.HISTORY.
- Produces: StoryboardScene, Storyboard, find_tone_result, build_storyboard, current_source_fingerprint.
- Consumed by: Tasks 4 and 6.

- [ ] **Step 1: Write failing storyboard, path-safety, and copy-safety tests**

~~~python
from pathlib import Path

import pytest

from app.backend.services.storyboard import build_storyboard


def test_storyboard_uses_only_stored_copy(seed_rush_hour_result, tmp_path):
    image = tmp_path / "data" / "outputs" / "card.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"image")
    board = build_storyboard(
        "res_abc123",
        output_root=image.parent,
        static_root=tmp_path / "data",
    )
    assert [scene.text for scene in board.scenes] == [
        "출근길 필수템",
        "가볍고 시원하게",
        "USB-C 충전 · 8시간 사용",
        "휴대용 선풍기\n지금 확인해보세요",
    ]
    assert all("할인" not in scene.text for scene in board.scenes)


def test_storyboard_rejects_output_path_escape(seed_rush_hour_result, tmp_path):
    seed_rush_hour_result["images"]["sns_card"] = "/files/../../secrets.txt"
    with pytest.raises(ValueError, match="허용된 출력 경로"):
        build_storyboard(
            "res_abc123",
            output_root=tmp_path / "data" / "outputs",
            static_root=tmp_path / "data",
        )
~~~

- [ ] **Step 2: Run the focused tests and verify RED**

~~~powershell
python -m pytest tests/test_storyboard.py -q
~~~

Expected: import failure because storyboard.py does not exist.

- [ ] **Step 3: Implement immutable storyboard data and safe source selection**

Create these complete public data types and functions:

~~~python
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.backend.services.store import HISTORY, PRODUCTS


@dataclass(frozen=True)
class StoryboardScene:
    text: str
    duration_sec: float
    accent_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class Storyboard:
    result_id: str
    product_id: str
    tone: str
    time_slot: str
    product_name: str
    image_path: Path
    scenes: tuple[StoryboardScene, ...]
    source_fingerprint: str


def find_tone_result(result_id: str) -> tuple[dict | None, dict | None]:
    for entry in HISTORY:
        for tone_result in entry.get("results", []):
            if tone_result.get("result_id") == result_id:
                return entry, tone_result
    return None, None


def build_storyboard(
    result_id: str,
    *,
    output_root: Path = Path("data/outputs"),
    static_root: Path = Path("data"),
) -> Storyboard:
    entry, tone_result = find_tone_result(result_id)
    if entry is None or tone_result is None:
        raise ValueError("result_id에 해당하는 생성 결과를 찾을 수 없습니다")
    if tone_result.get("time_slot") not in {"commute_am", "commute_pm"}:
        raise ValueError("쇼츠는 출근·퇴근 시간대 결과만 지원합니다")

    product = PRODUCTS.get(entry["product_id"], {})
    images = tone_result.get("images") or {}
    image_url = images.get("sns_card") or images.get("thumbnail")
    if image_url is None and images:
        image_url = next(iter(images.values()))
    if not image_url or not image_url.startswith("/files/outputs/"):
        raise ValueError("허용된 출력 경로의 광고 이미지가 필요합니다")

    resolved_output_root = output_root.resolve()
    image_path = (static_root.resolve() / image_url.removeprefix("/files/")).resolve()
    if not image_path.is_relative_to(resolved_output_root):
        raise ValueError("허용된 출력 경로 밖의 이미지는 사용할 수 없습니다")
    if not image_path.is_file():
        raise ValueError("광고 이미지 파일을 찾을 수 없습니다")

    selling_points = tuple(str(value) for value in product.get("selling_points", []) if value)
    scenes = [
        StoryboardScene(str(tone_result["headline"]), 2.5),
        StoryboardScene(str(tone_result["subcopy"]), 3.0),
    ]
    if selling_points:
        scenes.append(StoryboardScene(" · ".join(selling_points[:2]), 4.0, selling_points[:2]))
        cta_duration = 3.0
    else:
        cta_duration = 4.5
    product_name = str(product.get("product_name", "제품"))
    scenes.append(StoryboardScene(f"{product_name}\n지금 확인해보세요", cta_duration))

    fingerprint_payload = {
        "product_name": product_name,
        "headline": tone_result["headline"],
        "subcopy": tone_result["subcopy"],
        "selling_points": selling_points,
        "tone": tone_result["tone"],
        "time_slot": tone_result["time_slot"],
        "image_url": image_url,
        "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return Storyboard(
        result_id=result_id,
        product_id=entry["product_id"],
        tone=tone_result["tone"],
        time_slot=tone_result["time_slot"],
        product_name=product_name,
        image_path=image_path,
        scenes=tuple(scenes),
        source_fingerprint=fingerprint,
    )


def current_source_fingerprint(result_id: str) -> str:
    return build_storyboard(result_id).source_fingerprint
~~~

Implementation requirements:

- Prefer images.sns_card, then images.thumbnail, then the first image.
- Accept only /files/outputs/ URLs.
- Resolve both the static root and candidate path and require candidate.is_relative_to(output_root.resolve()).
- Include product name, headline, subcopy, selling points, tone, time_slot, image URL, and source image SHA-256 in a sorted UTF-8 JSON fingerprint.
- Use 2.5, 3.0, 4.0, and 3.0 second scenes when selling points exist.
- Omit the selling-point scene and use a 4.5 second CTA when selling points are absent.
- Keep compatibility exports in video_generation_service.py so existing imports fail loudly only after their tests are migrated.

- [ ] **Step 4: Run focused and compatibility tests**

~~~powershell
python -m pytest tests/test_storyboard.py tests/test_video_generation.py -q
~~~

Expected: PASS.

- [ ] **Step 5: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/backend/services/storyboard.py app/backend/services/video_generation_service.py tests/test_storyboard.py tests/test_video_generation.py
git commit -m "feat: build factual rush-hour storyboards"
~~~

---

### Task 3: Validate a Licensed Tone-Based Music Catalog

**Files:**
- Create: app/backend/services/music_catalog.py
- Create: assets/music/README.md
- Create: assets/music/manifest.example.json
- Create: tests/test_music_catalog.py
- Modify: .gitignore
- Modify: .env.example

**Interfaces:**
- Produces: MusicTrack, MusicCatalog.load, MusicCatalog.select_for_tone.
- Consumed by: Tasks 4 and 6.
- External prerequisite: before an actual YouTube scheduling smoke test, the project owner supplies or approves four audio files with cross-platform commercial-use evidence.

- [ ] **Step 1: Write failing catalog validation tests with temporary audio bytes**

~~~python
import hashlib
import json

import pytest

from app.backend.services.music_catalog import MusicCatalog


def test_catalog_selects_verified_track_for_tone(tmp_path):
    audio = tmp_path / "practical_upbeat_01.mp3"
    audio.write_bytes(b"licensed-test-audio")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"tracks": [{
        "key": "practical_upbeat_01",
        "file": audio.name,
        "tone": "practical",
        "title": "Practical Upbeat 01",
        "source_url": "https://license.example/track",
        "license": "Commercial license test fixture",
        "commercial_use": True,
        "attribution_required": False,
        "attribution_text": "",
        "sha256": digest,
        "bpm": 120,
    }]}), encoding="utf-8")
    catalog = MusicCatalog.load(manifest, asset_root=tmp_path)
    assert catalog.select_for_tone("practical").path == audio.resolve()


def test_catalog_rejects_noncommercial_track(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"tracks":[{"commercial_use":false}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="commercial_use"):
        MusicCatalog.load(manifest, asset_root=tmp_path)
~~~

- [ ] **Step 2: Run the focused tests and verify RED**

~~~powershell
python -m pytest tests/test_music_catalog.py -q
~~~

Expected: import failure because music_catalog.py does not exist.

- [ ] **Step 3: Implement strict manifest parsing**

~~~python
from pathlib import Path

from pydantic import BaseModel, Field


class MusicTrack(BaseModel):
    key: str = Field(min_length=1)
    file: str
    tone: str
    title: str
    source_url: str
    license: str
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
    def load(cls, manifest_path: Path, *, asset_root: Path) -> "MusicCatalog":
        manifest = MusicManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        resolved_root = asset_root.resolve()
        tracks_by_tone: dict[str, MusicTrack] = {}
        for track in manifest.tracks:
            if not track.commercial_use:
                raise ValueError(f"{track.key}: commercial_use must be true")
            if not track.source_url or not track.license:
                raise ValueError(f"{track.key}: source_url and license are required")
            if track.attribution_required and not track.attribution_text:
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
                raise ValueError(f"{track.tone}: exactly one active track is required")
            tracks_by_tone[track.tone] = track.model_copy(update={"path": path})
        expected_tones = {"emotional", "modern", "practical", "premium"}
        if set(tracks_by_tone) != expected_tones:
            raise ValueError("each supported tone requires exactly one active track")
        return cls(tracks_by_tone)

    def select_for_tone(self, tone: str) -> MusicTrack:
        try:
            return self._tracks_by_tone[tone]
        except KeyError as exc:
            raise ValueError(f"unsupported music tone: {tone}") from exc
~~~

Reject a track when:

- commercial_use is not true.
- attribution_required is true and attribution_text is empty.
- source_url or license is empty.
- the normalized file escapes asset_root.
- the file does not exist.
- the actual SHA-256 differs.
- a tone has zero or more than one active track.

- [ ] **Step 4: Add repository-safe asset rules**

Use .gitignore rules that keep real audio out while preserving documentation:

~~~gitignore
assets/music/*
!assets/music/README.md
!assets/music/manifest.example.json
~~~

Add .env.example keys:

~~~dotenv
MUSIC_ASSET_DIR=assets/music/private
MUSIC_MANIFEST_PATH=assets/music/private/manifest.json
~~~

The example manifest contains four exact keys and filenames but no assertion that the absent files are licensed:

~~~json
{
  "tracks": [
    {"key": "emotional_warm_01", "file": "emotional_warm_01.mp3", "tone": "emotional"},
    {"key": "modern_clean_01", "file": "modern_clean_01.mp3", "tone": "modern"},
    {"key": "practical_upbeat_01", "file": "practical_upbeat_01.mp3", "tone": "practical"},
    {"key": "premium_ambient_01", "file": "premium_ambient_01.mp3", "tone": "premium"}
  ]
}
~~~

README.md must state that the example is not loadable until every required license and hash field is completed in the private manifest.

- [ ] **Step 5: Run focused tests and secret/artifact checks**

~~~powershell
python -m pytest tests/test_music_catalog.py -q
git status --short
git ls-files assets/music
~~~

Expected: tests PASS; only README.md and manifest.example.json are trackable; no MP3, WAV, OAuth, or token file is listed.

- [ ] **Step 6: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add .gitignore .env.example app/backend/services/music_catalog.py assets/music/README.md assets/music/manifest.example.json tests/test_music_catalog.py
git commit -m "feat: validate licensed video music"
~~~

---

### Task 4: Render and Verify Real 9:16 MP4 Files

**Files:**
- Create: app/backend/services/video_renderer.py
- Create: tests/test_video_renderer.py
- Modify: pyproject.toml
- Modify: requirements.txt
- Modify: .github/workflows/test.yml
- Modify: SETUP.md

**Interfaces:**
- Consumes: Storyboard and optional MusicTrack.
- Produces: RenderResult and RushHourVideoRenderer.render.
- Consumed by: Task 6.

- [ ] **Step 1: Keep Pillow compatible with rembg and verify FFmpeg**

Do not add MoviePy: MoviePy 2.2.1 requires Pillow below 12 while rembg 2.0.76 requires Pillow 12.1 or newer. Keep the shared exact Pillow pin:

~~~toml
[project]
dependencies = [
    "pillow==12.2.0",
]
~~~

Use the same direct pin in requirements.txt. Keep all newly introduced Google dependencies for Task 5 exact-pinned there as one atomic dependency update:

~~~text
pillow==12.2.0
google-api-python-client==2.198.0
google-auth-oauthlib==1.4.0
google-auth-httplib2==0.4.1
~~~

Add a CI step before pytest:

~~~yaml
- name: Verify FFmpeg runtime
  run: |
    ffmpeg -version
    ffprobe -version
~~~

SETUP.md must show Windows and Ubuntu verification commands without claiming FFmpeg is installed when the commands fail.

- [ ] **Step 2: Write a failing real-render integration test**

Generate a tiny image and WAV fixture inside tmp_path so tests do not download or commit media:

~~~python
from pathlib import Path
import wave

from PIL import Image

from app.backend.services.storyboard import Storyboard, StoryboardScene
from app.backend.services.video_renderer import RushHourVideoRenderer


def _write_silence(path: Path, seconds: float = 1.0) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x00\x00\x00\x00" * int(44100 * seconds))


def test_renderer_outputs_verified_vertical_mp4(tmp_path):
    image_path = tmp_path / "card.png"
    Image.new("RGB", (1080, 1350), "#315a78").save(image_path)
    music_path = tmp_path / "music.wav"
    _write_silence(music_path, 2.0)
    board = Storyboard(
        result_id="res_1",
        product_id="prd_1",
        tone="practical",
        time_slot="commute_am",
        product_name="휴대용 선풍기",
        image_path=image_path,
        scenes=(
            StoryboardScene("출근길 필수템", 2.5),
            StoryboardScene("가볍고 시원하게", 3.0),
            StoryboardScene("USB-C 충전", 4.0),
            StoryboardScene("지금 확인해보세요", 3.0),
        ),
        source_fingerprint="a" * 64,
    )
    result = RushHourVideoRenderer(font_path=Path("assets/fonts/NanumGothic-Regular.ttf")).render(
        board,
        output_path=tmp_path / "video_1.mp4",
        music_path=music_path,
    )
    assert result.output_path.stat().st_size > 0
    assert result.width == 1080
    assert result.height == 1920
    assert 10.0 <= result.duration_sec <= 15.0
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
~~~

- [ ] **Step 3: Run the renderer test and verify RED**

~~~powershell
python -m pytest tests/test_video_renderer.py::test_renderer_outputs_verified_vertical_mp4 -q
~~~

Expected: import failure because video_renderer.py does not exist.

- [ ] **Step 4: Implement focused renderer helpers**

Create these exact interfaces:

~~~python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    sha256: str
    duration_sec: float
    width: int
    height: int
    video_codec: str
    audio_codec: str
    music_warning: str | None


class RushHourVideoRenderer:
    def __init__(
        self,
        *,
        font_path: Path,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
    ) -> None:
        self._font_path = font_path
        self._ffmpeg_bin = ffmpeg_bin
        self._ffprobe_bin = ffprobe_bin

    def render(
        self,
        storyboard: Storyboard,
        *,
        output_path: Path,
        music_path: Path | None,
    ) -> RenderResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        video_only = output_path.with_name(f"{output_path.stem}.video-only.mp4")
        try:
            self._write_video_only(storyboard, video_only)
            music_warning = self._mux_audio(video_only, output_path, music_path)
            metadata = self._probe(output_path)
            self._validate_probe(metadata)
            return RenderResult(
                output_path=output_path,
                sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
                duration_sec=metadata["duration_sec"],
                width=metadata["width"],
                height=metadata["height"],
                video_codec=metadata["video_codec"],
                audio_codec=metadata["audio_codec"],
                music_warning=music_warning,
            )
        finally:
            video_only.unlink(missing_ok=True)
~~~

Split internals into:

- _make_scene_frame(scene, source_image, tone) -> numpy.ndarray.
- _wrap_text(text, font, max_width) -> list[str].
- _validate_safe_area(draw, lines, bounds) -> None.
- _write_video_only(storyboard, temporary_path) -> None.
- _mux_audio(video_path, output_path, music_path) -> str | None.
- _probe(output_path) -> dict.

Use Pillow to compose each complete 1080x1920 frame:

- Fill the canvas with a cover-scaled Gaussian-blurred copy.
- Fit the original 4:5 image inside the canvas without cropping.
- Put text only inside x=86..994, y=192..1632.
- Use tone accent colors from a local constant.
- Apply a maximum 1.5 percent zoom across each scene; reject any transform that would move the fitted product image outside its protected rectangle.

Write one Pillow PNG per scene, then invoke FFmpeg with argument lists and never shell=True. Use loop=1, the exact scene duration, scale/zoompan, 1080x1920 output, 30fps, libx264, yuv420p, and concat demuxing for scene timing. For music:

~~~python
fade_out_at = max(total_duration_sec - 0.5, 0.0)
[
    ffmpeg_bin, "-y",
    "-i", str(video_only),
    "-stream_loop", "-1", "-i", str(music_path),
    "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "copy", "-c:a", "aac",
    "-filter:a",
    f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.5,"
    f"afade=t=out:st={fade_out_at}:d=0.5",
    "-shortest", str(output_path),
]
~~~

For missing music, mux anullsrc as AAC and return music_warning="music_unavailable". Probe the final file and raise RuntimeError unless dimensions, duration, H.264, and AAC match the global constraints.

- [ ] **Step 5: Run renderer and full regression tests**

~~~powershell
python -m pytest tests/test_video_renderer.py -q
python -m pytest -q
~~~

Expected: renderer tests PASS and the full suite has zero failures.

- [ ] **Step 6: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/backend/services/video_renderer.py tests/test_video_renderer.py pyproject.toml requirements.txt .github/workflows/test.yml SETUP.md
git commit -m "feat: render verified rush-hour shorts"
~~~

---

### Task 5: Isolate YouTube Authentication and Scheduled Uploads

**Files:**
- Create: app/backend/services/youtube_publisher.py
- Create: scripts/authorize_youtube.py
- Create: tests/test_youtube_publisher.py
- Modify: .env.example
- Modify: .gitignore

**Interfaces:**
- Produces: PublishRequest, Publisher protocol, DisabledPublisher, GoogleYouTubePublisher.
- Consumed by: Task 6.

- [ ] **Step 1: Write failing request-body, validation, and no-network tests**

~~~python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.backend.services.youtube_publisher import (
    GoogleYouTubePublisher,
    PublishRequest,
)


def test_publish_body_is_private_and_scheduled(tmp_path):
    service = FakeYouTubeService(video_id="yt_123")
    publisher = GoogleYouTubePublisher(service_factory=lambda: service)
    video = tmp_path / "short.mp4"
    video.write_bytes(b"mp4")
    request = PublishRequest(
        video_path=video,
        title="휴대용 선풍기 | 출근길 필수템",
        description="가볍고 시원하게\n\n#Shorts",
        tags=("Shorts", "제품광고"),
        publish_at=datetime(2026, 8, 10, 8, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )
    assert publisher.publish(request) == "yt_123"
    body = service.insert_calls[0]["body"]
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == "2026-08-09T23:00:00Z"
    assert body["status"]["containsSyntheticMedia"] is True
~~~

Also test:

- DisabledPublisher raises AuthenticationRequired without touching the network.
- A missing video file is rejected before service creation.
- A naive datetime is rejected.
- A past datetime is rejected.
- 500, 502, 503, and 504 are retried at most three times.
- Non-retriable 400 is returned immediately as PublishRejected.

- [ ] **Step 2: Run focused tests and verify RED**

~~~powershell
python -m pytest tests/test_youtube_publisher.py -q
~~~

Expected: import failure because youtube_publisher.py does not exist.

- [ ] **Step 3: Implement the publisher protocol and request**

~~~python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PublishRequest:
    video_path: Path
    title: str
    description: str
    tags: tuple[str, ...]
    publish_at: datetime


@dataclass(frozen=True)
class PublisherStatus:
    configured: bool
    connection_id: str
    token_available: bool


class Publisher(Protocol):
    def status(self) -> PublisherStatus:
        raise NotImplementedError

    def publish(self, request: PublishRequest) -> str:
        raise NotImplementedError
~~~

GoogleYouTubePublisher must:

- Receive a service_factory dependency for testability.
- Build the service lazily.
- Return PublisherStatus from status without exposing token or credential paths.
- Use MediaFileUpload with resumable=True.
- Convert aware publish_at to UTC RFC 3339 ending in Z.
- Send privacyStatus=private, selfDeclaredMadeForKids=false, and containsSyntheticMedia=true.
- Return the YouTube video ID only after the insert response contains a non-empty id.
- Raise AuthenticationRequired, ScheduleExpired, PublishRejected, or PublishUncertain with sanitized messages.
- Never log credential objects, token contents, client secrets, or full API response bodies.

- [ ] **Step 4: Add one-time operator OAuth bootstrap**

scripts/authorize_youtube.py must:

- Read YOUTUBE_CLIENT_SECRETS_FILE and YOUTUBE_TOKEN_FILE from environment.
- Use only https://www.googleapis.com/auth/youtube.upload.
- Run InstalledAppFlow.run_local_server on localhost.
- Write credentials.to_json() to a temporary sibling file and atomically replace the token file.
- Create the token parent directory and print only the final path and scope.
- Refuse to write inside the repository root or data directory.

Add:

~~~dotenv
YOUTUBE_CLIENT_SECRETS_FILE=
YOUTUBE_TOKEN_FILE=
YOUTUBE_CONNECTION_ID=demo_merchant_channel
YOUTUBE_UPLOAD_ENABLED=false
~~~

Add ignore guards:

~~~gitignore
client_secrets*.json
youtube_token*.json
token.pickle
~~~

- [ ] **Step 5: Run focused tests and credential scans**

~~~powershell
python -m pytest tests/test_youtube_publisher.py -q
rg -n "client_secret|refresh_token|token.pickle" . -g "!docs/superpowers/**" -g "!.git/**"
~~~

Expected: tests PASS; matches are limited to ignore rules, configuration labels, and safe documentation, with no credential values.

- [ ] **Step 6: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/backend/services/youtube_publisher.py scripts/authorize_youtube.py tests/test_youtube_publisher.py .env.example .gitignore
git commit -m "feat: add safe YouTube scheduling adapter"
~~~

---

### Task 6: Orchestrate Rendering, Approval, Rejection, and Publishing

**Files:**
- Create: app/backend/services/video_workflow.py
- Create: tests/test_video_workflow.py
- Modify: app/backend/services/video_generation_service.py
- Modify: app/backend/main.py

**Interfaces:**
- Consumes: VideoJob, build_storyboard, MusicCatalog, RushHourVideoRenderer, Publisher, store.VIDEO_JOBS.
- Produces: VideoWorkflowService.create, run_render, get, approve, run_publish, reject, youtube_status.
- Consumed by: Tasks 7-9.

- [ ] **Step 1: Write failing state-machine and integrity tests**

~~~python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest


def test_approval_requires_completed_render(workflow, seed_video_job):
    seed_video_job["render_status"] = "processing"
    with pytest.raises(WorkflowConflict, match="렌더링 완료"):
        workflow.approve(
            seed_video_job["video_job_id"],
            activation_at=datetime.now(ZoneInfo("Asia/Seoul")) + timedelta(days=1),
            publish_to_youtube=False,
            allow_silent=False,
        )


def test_youtube_failure_keeps_internal_approval(workflow_with_failing_publisher, completed_video_job):
    job = workflow_with_failing_publisher.approve(
        completed_video_job["video_job_id"],
        activation_at=next_commute_am(),
        publish_to_youtube=True,
        allow_silent=False,
    )
    workflow_with_failing_publisher.run_publish(job.video_job_id)
    stored = workflow_with_failing_publisher.get(job.video_job_id)
    assert stored.approval_status == "approved"
    assert stored.publish_status == "failed"
~~~

Also test:

- create rejects non-rush-hour and duplicate active result jobs.
- run_render persists processing before invoking the renderer.
- run_render stores the MP4 hash and music warning.
- approval recalculates source and video hashes and rejects changes.
- music_warning requires allow_silent=true.
- commute slot/date validation and 10-minute lead time.
- identical approval is idempotent.
- different approval after scheduling is rejected.
- reject works only while approval_status=pending.
- process restart leaves uncertain uploads for manual review.

- [ ] **Step 2: Run focused tests and verify RED**

~~~powershell
python -m pytest tests/test_video_workflow.py -q
~~~

Expected: import failure because video_workflow.py does not exist.

- [ ] **Step 3: Implement the injected workflow service**

Initialize the service and its locks exactly once:

~~~python
class VideoWorkflowService:
    def __init__(
        self,
        *,
        renderer: RushHourVideoRenderer,
        music_catalog: MusicCatalog | None,
        publisher: Publisher,
        now: Callable[[], datetime],
        video_dir: Path = Path("data/videos"),
    ) -> None:
        self._renderer = renderer
        self._music_catalog = music_catalog
        self._publisher = publisher
        self._now = now
        self._video_dir = video_dir
        self._state_lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._publish_lock = threading.Lock()
~~~

Add these exact public methods:

- create(self, result_id: str) -> VideoJob: validate the storyboard, reject an active duplicate, persist a queued job, and return it.
- run_render(self, video_job_id: str) -> None: persist processing, render outside the state lock, then persist completed metadata or a sanitized failure.
- get(self, video_job_id: str) -> VideoJob: validate the stored dictionary and return a VideoJob; raise WorkflowNotFound when absent.
- approve(self, video_job_id: str, *, activation_at: datetime, publish_to_youtube: bool, allow_silent: bool) -> VideoJob: perform integrity and scheduling checks, persist approval, and set publish_status to pending or not_requested.
- run_publish(self, video_job_id: str) -> None: publish outside the state lock and persist scheduled or the mapped typed failure.
- reject(self, video_job_id: str) -> VideoJob: allow only pending approval and persist rejected.
- youtube_status(self) -> dict[str, str | bool]: map publisher.status() to configured, connection_id, and token_available without paths.

Use one threading.Lock for state mutations and separate non-blocking locks for renderer and publisher execution. Never hold the state lock while rendering, hashing a large file, or calling YouTube.

Mutation pattern:

1. Acquire state lock.
2. Validate current state and write the next durable state.
3. Call store.save().
4. Release lock.
5. Perform expensive/external work.
6. Reacquire lock, store result, save, and release.

run_publish catches typed publisher exceptions and maps them:

- AuthenticationRequired -> auth_required.
- ScheduleExpired -> schedule_expired.
- PublishUncertain -> needs_review.
- PublishRejected or exhausted retriable errors -> failed.

- [ ] **Step 4: Wire a safe default service at application startup**

In app/backend/main.py build:

- DisabledPublisher unless YOUTUBE_UPLOAD_ENABLED=true and credential paths are configured.
- MusicCatalog only when the private manifest is present and valid; otherwise pass None so rendering creates a warned silent preview.
- RushHourVideoRenderer with the project font and configured FFmpeg executable names.
- One VideoWorkflowService stored in app.state.video_workflow.

Do not execute OAuth during import or startup.

- [ ] **Step 5: Run focused and full regression tests**

~~~powershell
python -m pytest tests/test_video_workflow.py tests/test_video_generation.py -q
python -m pytest -q
~~~

Expected: all tests PASS.

- [ ] **Step 6: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/backend/services/video_workflow.py app/backend/services/video_generation_service.py app/backend/main.py tests/test_video_workflow.py
git commit -m "feat: orchestrate video approval workflow"
~~~

---

### Task 7: Expose the Video and Approval API

**Files:**
- Modify: app/backend/api/videos.py
- Create: app/backend/api/youtube.py
- Create: tests/test_video_api.py
- Modify: tests/test_api.py
- Modify: app/backend/main.py

**Interfaces:**
- Consumes: app.state.video_workflow and video schemas.
- Produces: POST /videos, GET /videos/{id}, POST /videos/{id}/approve, POST /videos/{id}/reject, GET /youtube/status.
- Consumed by: Task 9.

- [ ] **Step 1: Write failing API contract tests**

~~~python
def test_create_video_returns_202(client, rush_hour_result_id):
    response = client.post("/api/v1/videos", json={"result_id": rush_hour_result_id})
    assert response.status_code == 202
    assert response.json()["render_status"] == "queued"


def test_approve_video_returns_202_and_does_not_upload_inline(
    client, completed_video_job, fake_publisher
):
    response = client.post(
        f"/api/v1/videos/{completed_video_job}/approve",
        json={
            "activation_at": "2026-08-10T08:00:00+09:00",
            "publish_to_youtube": True,
            "allow_silent": False,
        },
    )
    assert response.status_code == 202
    assert response.json()["approval_status"] == "approved"
    assert response.json()["publish_status"] == "pending"
~~~

Also assert:

- unknown result and job return 404.
- non-rush-hour result returns 400.
- state, integrity, duplicate, and silent-confirmation conflicts return 409.
- invalid datetime/slot/lead time returns 422.
- internal exceptions are not exposed.
- status response never contains token paths or credential data.
- YouTube status returns configured, connection_id, and token_available only.

- [ ] **Step 2: Run focused API tests and verify RED**

~~~powershell
python -m pytest tests/test_video_api.py -q
~~~

Expected: failures because the current API returns the Mock schema and has no approval endpoints.

- [ ] **Step 3: Replace Mock endpoint behavior with workflow calls**

Use FastAPI BackgroundTasks:

~~~python
@router.post("", response_model=VideoCreateResponse, status_code=202)
async def create_video(
    req: VideoCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> VideoCreateResponse:
    workflow = request.app.state.video_workflow
    job = workflow.create(req.result_id)
    background_tasks.add_task(workflow.run_render, job.video_job_id)
    return VideoCreateResponse(
        video_job_id=job.video_job_id,
        render_status=job.render_status,
    )
~~~

Approval stores the approved state synchronously, then adds run_publish only when publish_status is pending. Map typed workflow exceptions to the exact 404, 400, 409, and 422 status codes listed above.

Create app/backend/api/youtube.py with prefix /api/v1/youtube and GET /status. Include that router in app/backend/main.py. Keep it separate from the /videos/{video_job_id} route.

- [ ] **Step 4: Run API and full regression tests**

~~~powershell
python -m pytest tests/test_video_api.py tests/test_api.py -q
python -m pytest -q
~~~

Expected: all tests PASS and obsolete Mock assertions are removed rather than weakened.

- [ ] **Step 5: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/backend/api/videos.py app/backend/api/youtube.py app/backend/main.py tests/test_video_api.py tests/test_api.py
git commit -m "feat: expose video approval API"
~~~

---

### Task 8: Return the Latest Eligible Video During Rush Hour

**Files:**
- Modify: app/backend/services/exposure.py
- Modify: app/backend/api/exposure.py
- Modify: tests/test_exposure.py

**Interfaces:**
- Consumes: store.VIDEO_JOBS and current KST.
- Produces: pick_video_exposure and exposure response video field.
- Consumed by: Task 9 and signage clients.

- [ ] **Step 1: Write failing selection tests**

~~~python
def test_pick_exposure_returns_latest_approved_active_video():
    now = datetime(2026, 8, 10, 8, 30)
    jobs = {
        "older": {
            "video_job_id": "older",
            "product_id": "prd_1",
            "time_slot": "commute_am",
            "render_status": "completed",
            "approval_status": "approved",
            "activation_at": "2026-08-09T08:00:00+09:00",
            "approved_at": "2026-08-08T12:00:00+09:00",
            "video_url": "/files/videos/older.mp4",
        },
        "latest": {
            "video_job_id": "latest",
            "product_id": "prd_1",
            "time_slot": "commute_am",
            "render_status": "completed",
            "approval_status": "approved",
            "activation_at": "2026-08-10T08:00:00+09:00",
            "approved_at": "2026-08-09T12:00:00+09:00",
            "video_url": "/files/videos/latest.mp4",
        },
    }
    response = pick_exposure("prd_1", history=[], video_jobs=jobs, now=now)
    assert response["video"]["video_job_id"] == "latest"
~~~

Also test no video when:

- current slot is not commute_am or commute_pm.
- approval_status is pending or rejected.
- render_status is not completed.
- activation_at is in the future.
- product or time_slot differs.
- video_url is absent.

Add a test proving publish_status=failed still permits internal exposure.

- [ ] **Step 2: Run focused tests and verify RED**

~~~powershell
python -m pytest tests/test_exposure.py -q
~~~

Expected: failure because pick_exposure does not accept video_jobs and returns no video field.

- [ ] **Step 3: Implement latest eligible selection**

Add a focused helper and call it from the existing banner-selection flow:

~~~python
def pick_video_exposure(
    product_id: str,
    *,
    time_slot: str,
    video_jobs: dict[str, dict],
    now: datetime,
) -> dict | None:
    if time_slot not in {"commute_am", "commute_pm"}:
        return None
    candidates = []
    for job in video_jobs.values():
        activation_at = datetime.fromisoformat(job["activation_at"]) if job.get("activation_at") else None
        if (
            job.get("product_id") == product_id
            and job.get("time_slot") == time_slot
            and job.get("render_status") == "completed"
            and job.get("approval_status") == "approved"
            and job.get("video_url")
            and activation_at is not None
            and activation_at.astimezone(KST) <= now
        ):
            candidates.append(job)
    if not candidates:
        return None
    selected = max(
        candidates,
        key=lambda job: (job.get("approved_at", ""), job.get("updated_at", "")),
    )
    return {
        "video_job_id": selected["video_job_id"],
        "video_url": selected["video_url"],
    }
~~~

Change pick_exposure to accept video_jobs: dict[str, dict] | None = None, normalize now to KST once, preserve the existing banner result, and set result["video"] from pick_video_exposure. Add video=None outside rush-hour slots or when no candidate exists.

Modify the API to pass store.VIDEO_JOBS explicitly.

- [ ] **Step 4: Run exposure and full regression tests**

~~~powershell
python -m pytest tests/test_exposure.py tests/test_api.py -q
python -m pytest -q
~~~

Expected: all tests PASS.

- [ ] **Step 5: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/backend/services/exposure.py app/backend/api/exposure.py tests/test_exposure.py
git commit -m "feat: expose approved rush-hour videos"
~~~

---

### Task 9: Add Preview, Approval, Rejection, and Scheduling UI

**Files:**
- Modify: app/frontend/pages/3_History.py
- Create: tests/test_history_video_ui_contract.py

**Interfaces:**
- Consumes: Task 7 API endpoints.
- Produces: operator-facing approval workflow in History.

- [ ] **Step 1: Write a failing source-contract test for critical UI controls**

~~~python
from pathlib import Path


def test_history_page_contains_video_approval_contract():
    source = Path("app/frontend/pages/3_History.py").read_text(encoding="utf-8")
    assert "/approve" in source
    assert "/reject" in source
    assert "publish_to_youtube" in source
    assert "allow_silent" in source
    assert "activation_at" in source
    assert "승인 전에는 게시되지 않습니다" in source
~~~

- [ ] **Step 2: Run the UI contract test and verify RED**

~~~powershell
python -m pytest tests/test_history_video_ui_contract.py -q
~~~

Expected: failure because the current History page only creates and displays the Mock video.

- [ ] **Step 3: Extract small UI helpers inside the page**

Add:

~~~python
def api_url(path: str) -> str:
    return f"{API_BASE}{path}"


def default_activation_at(time_slot: str, now: datetime) -> datetime:
    kst_now = now.astimezone(ZoneInfo("Asia/Seoul"))
    target_time = time(8, 0) if time_slot == "commute_am" else time(18, 0)
    candidate = datetime.combine(kst_now.date(), target_time, tzinfo=kst_now.tzinfo)
    if candidate < kst_now + timedelta(minutes=10):
        candidate += timedelta(days=1)
    return candidate
~~~

Add render_video_workflow(result: dict) -> None as the only function that reads and writes Streamlit session keys for one result. It calls the API endpoints listed below and renders controls solely from the returned job state.

UI behavior:

- Show create button only for rush-hour results.
- Poll render_status and show queued, processing, failed, or completed.
- Show st.video only after a non-empty video_url.
- Show music_warning next to an explicit 무음으로 게시 checkbox.
- Prepopulate the next 08:00 or 18:00 KST date/time.
- Show publish_to_youtube checkbox only when GET /youtube/status reports configured=true.
- Display channel connection_id, not tokens or file paths.
- Display 승인 전에는 게시되지 않습니다 above the approval button.
- Approval POST sends activation_at with +09:00 offset, publish_to_youtube, and allow_silent.
- Reject POST requires a confirmation checkbox.
- YouTube failure appears separately from internal approval.
- Never auto-submit approval after rerun.

- [ ] **Step 4: Run UI contract and full regression tests**

~~~powershell
python -m pytest tests/test_history_video_ui_contract.py -q
python -m pytest -q
~~~

Expected: all tests PASS.

- [ ] **Step 5: Run manual local UI validation without YouTube**

Run in separate terminals:

~~~powershell
$env:YOUTUBE_UPLOAD_ENABLED="false"
uvicorn app.backend.main:app --reload --port 8000
~~~

~~~powershell
streamlit run app/frontend/streamlit_app.py
~~~

Verify:

1. A rush-hour result renders a real MP4.
2. Preview does not imply approval.
3. Missing music shows the warning and blocks approval until allow_silent is checked.
4. Approved video is returned by the exposure endpoint only for the matching simulated KST slot.
5. No YouTube request occurs.

- [ ] **Step 6: Local checkpoint when the no-git hold is lifted**

~~~powershell
git add app/frontend/pages/3_History.py tests/test_history_video_ui_contract.py
git commit -m "feat: add shorts approval interface"
~~~

---

### Task 10: Update Contracts and Run Release-Gate Verification

**Files:**
- Modify: docs/api_contract.md
- Modify: docs/integration_checklist.md
- Modify: SETUP.md
- Modify: app/backend/README.md

**Interfaces:**
- Documents every API, environment key, manual gate, and unverified external condition.
- Produces the evidence package for PM review.

- [ ] **Step 1: Update the API contract with exact requests and responses**

Document:

- POST /api/v1/videos returns 202 and render_status.
- GET /api/v1/videos/{id} returns separated render, approval, and publish states.
- POST /approve and /reject status codes and conflict rules.
- GET /youtube/status safe fields.
- exposure response video field.
- KST slot ranges, 10-minute lead time, silent confirmation, idempotency, and restart recovery.

- [ ] **Step 2: Update setup and integration gates**

SETUP.md must include:

- ffmpeg -version and ffprobe -version.
- pip install -e ".[video]".
- private music manifest placement.
- YOUTUBE_UPLOAD_ENABLED=false default.
- local OAuth bootstrap command only after explicit user authorization.

integration_checklist.md must distinguish:

- Automated and locally verified.
- Requires approved music assets.
- Requires team test channel OAuth.
- Requires explicit user approval for a private upload.
- Requires explicit user approval for a future scheduled publication.
- Not verified: API-project audit/publication eligibility until live evidence exists.

- [ ] **Step 3: Run the complete automated gate**

~~~powershell
python -m pytest -q
python -m ruff check app tests scripts
python -m compileall -q app scripts
python -m pip check
git diff --check
~~~

Expected:

- pytest exits 0 with zero failures.
- Ruff exits 0.
- compileall exits 0.
- pip check reports no broken requirements.
- git diff --check produces no output.

- [ ] **Step 4: Run media and secret gates**

~~~powershell
ffmpeg -version
ffprobe -version
git status --short
git ls-files | rg "\.(mp3|wav|m4a|aac|mp4|pickle)$"
rg -n "(client_secret|refresh_token|private_key)" . -g "!.git/**" -g "!docs/superpowers/**"
~~~

Expected:

- FFmpeg and ffprobe exit 0.
- No generated video, real music, token, pickle, or secret file is tracked.
- Secret scan has no credential values.

- [ ] **Step 5: Perform external checks only after separate explicit approval**

The external sequence is:

1. Confirm the exact team test channel and OAuth account with the user.
2. Run scripts/authorize_youtube.py locally; never in CI.
3. Render one commute_am and one commute_pm video with approved licensed tracks.
4. Upload one video as private and record its YouTube video ID.
5. Show title, description, channel, privacy state, synthetic-media flag, and scheduled KST time to the user.
6. Only after a second explicit approval, schedule one future publication.
7. Do not delete, cancel, publish immediately, push code, or open a PR without separate authorization.

- [ ] **Step 6: Prepare the PM handoff without publishing**

Report:

- Automated test counts and commands.
- ffprobe metadata for the two sample videos.
- Music manifest evidence and hashes.
- The exact internal exposure test times.
- Private-upload result if authorized.
- Scheduled-publication result if authorized.
- Remaining unverified conditions.

- [ ] **Step 7: Final local checkpoint only after the no-git hold is lifted**

~~~powershell
git add docs/api_contract.md docs/integration_checklist.md SETUP.md app/backend/README.md
git commit -m "docs: document shorts release gates"
~~~

Do not push, create a PR, or merge until the user explicitly requests it.

## Execution Order and Review Gates

1. Tasks 1-4 produce a real local video with persisted state and no external calls.
2. Review Gate A: inspect one commute_am and one commute_pm MP4 before adding live credentials.
3. Tasks 5-8 add the safe publishing boundary, approval state machine, API, and internal exposure.
4. Task 9 adds operator controls.
5. Review Gate B: run the full app with YouTube disabled and verify approval behavior.
6. Task 10 completes documentation and automated validation.
7. Review Gate C: obtain explicit approval before OAuth, private upload, or future scheduling.
8. Review Gate D: obtain explicit approval before any push or PR.

## Definition of Done

- The full local test suite and static checks pass.
- Two real 10-15 second 1080x1920 H.264/AAC sample videos are inspected.
- Product images are fit without crop and Korean text stays inside safe margins.
- TTS and narration are absent.
- Unverified music assets are not tracked or used.
- Approval is required before exposure and upload.
- Internal exposure works independently of YouTube status.
- The YouTube adapter is fully covered by fake-service tests.
- Live OAuth, private upload, and scheduled publication are reported only when separately authorized and directly observed.
- No shorts code, media, commit, push, or PR is published while the current user hold remains active.
