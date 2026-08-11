# Rush-Hour Deadpan AI Comic Shorts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PR #17's music-and-caption Shorts renderer with an opt-in rush-hour workflow that uses three high-quality product images, accurate Korean TTS, one deadpan AI self-aware comedy beat, intentional silence, synchronized captions, human approval, and optional YouTube scheduling.

**Architecture:** Keep `model_server` and its `/infer` contract unchanged. The backend reuses the already-generated hero image and makes two additional sequential `/infer` calls through a new scene-image adapter, then builds a rule-based factual script, synthesizes sentence WAV files through a lazy MeloTTS adapter, and performs one FFmpeg render. Existing approval, integrity, exposure, and YouTube boundaries remain, while music-specific schema and services are removed from the Draft branch.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, Pillow, FFmpeg/ffprobe, httpx, MeloTTS-Korean on CPU, pytest, Streamlit.

## Global Constraints

- Do not modify any file under `model_server/` or change `POST /infer` request/response fields.
- Use the current serving profile `fast_composite`, 768 background, 4 steps; make model calls sequentially.
- Reuse the existing approved hero image and generate exactly two extra scene images, yielding three unique images and four scenes.
- Use exactly one AI self-awareness beat of one or two consecutive short sentences and at most 35 percent of spoken duration.
- Pronunciation and grammar must be correct; comedy comes from the approved synthetic voice preset and silence.
- Do not render background music, sound effects, black caption boxes, or a music/caption fallback.
- Block approval on missing TTS, unreviewed product pronunciation, fewer than three images, stale sources, invalid media, or failed product preservation.
- Keep YouTube disabled by default and require explicit human approval.
- Keep model weights, WAV, MP4, OAuth material, and generated images outside Git.
- Pin MeloTTS source revision `209145371cff8fc3bd60d7be902ea69cbdb7965a` and Korean model revision `0207e5adfc90129a51b6b03d89be6d84360ed323`; record downloaded file hashes.
- Address PM review: queued publishing must not leave `publish_status=pending`, docs must say service-wide render serialization, and UI contract coverage must verify executable behavior rather than source strings alone.

---

### Task 1: Rule-Based Comic Script and Pronunciation Lexicon

**Files:**
- Create: `app/backend/services/comic_script.py`
- Create: `tests/test_comic_script.py`
- Modify: `app/backend/services/storyboard.py`
- Modify: `tests/test_storyboard.py`

**Interfaces:**
- Consumes: product name, selling points, `commute_am | commute_pm`.
- Produces: `ComicLine(display_text: str, spoken_text: str, kind: LineKind)`, `ComicScript(lines: tuple[ComicLine, ...], version: str)`, `PronunciationLexicon.resolve(text: str) -> PronunciationResult`.

- [ ] **Step 1: Write failing script tests**

```python
def test_script_has_one_self_aware_beat_and_factual_cta():
    script = build_comic_script(
        product_name="테스트 전자레인지",
        selling_points=("간편 조리",),
        time_slot="commute_am",
        lexicon=PronunciationLexicon({"테스트 전자레인지": "테스트 전자레인지"}),
    )
    assert [line.kind for line in script.lines] == [
        LineKind.INTRO,
        LineKind.SELF_AWARE,
        LineKind.BENEFIT,
        LineKind.CTA,
    ]
    assert script.lines[-1].display_text.endswith("확인해 보세요.")


def test_unknown_product_pronunciation_requires_review():
    result = PronunciationLexicon({}).resolve("ABC-1200")
    assert result.review_required is True
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m pytest tests/test_comic_script.py tests/test_storyboard.py -q`

Expected: collection or assertion failure because comic-script types are absent.

- [ ] **Step 3: Implement immutable script and pronunciation types**

Use frozen slotted dataclasses and an enum. Keep display and spoken text separate. Build four lines from curated time-slot templates and at most one stored selling point; never interpolate price, discount, or numeric performance values.

- [ ] **Step 4: Replace fixed headline/subcopy scenes in `build_storyboard`**

Extend each `StoryboardScene` with `spoken_text`, `kind`, and `image_purpose`. Extend `Storyboard` with `script_version` and `pronunciation_review_required`. Include those values in `source_fingerprint`.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_comic_script.py tests/test_storyboard.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/backend/services/comic_script.py app/backend/services/storyboard.py tests/test_comic_script.py tests/test_storyboard.py
git commit -m "feat: add deadpan comic Shorts scripts"
```

### Task 2: Pinned Korean TTS Adapter and Evaluation Harness

**Files:**
- Create: `app/backend/services/tts_provider.py`
- Create: `tools/evaluate_korean_tts.py`
- Create: `tests/test_tts_provider.py`
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `spoken_text`, destination WAV path, `DeadpanVoicePreset`.
- Produces: `TTSAudio(path: Path, duration_sec: float, sha256: str, engine: str, voice_preset: str)`.

- [ ] **Step 1: Write failing adapter tests using an injected fake engine**

```python
def test_provider_writes_wav_and_returns_hash(tmp_path):
    engine = FakeMeloEngine(sample_rate=24000)
    provider = MeloTTSProvider(engine_factory=lambda: engine)
    audio = provider.synthesize("정확하게 읽습니다.", tmp_path / "line.wav")
    assert audio.path.is_file()
    assert audio.duration_sec > 0
    assert len(audio.sha256) == 64
```

Also test lazy single-load, empty text rejection, output-path containment, and stable voice parameters.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m pytest tests/test_tts_provider.py -q`

Expected: import failure because the provider does not exist.

- [ ] **Step 3: Implement the provider boundary**

Use a `TTSProvider` protocol and lazy `MeloTTSProvider`. Instantiate `melo.api.TTS(language="KR", device="cpu", config_path=..., ckpt_path=...)` only on the first synthesis. Read explicit local model paths from `MELOTTS_CONFIG_PATH` and `MELOTTS_CHECKPOINT_PATH`; never allow implicit downloads in the service process. Read the Korean speaker id from `engine.hps.data.spk2id` and use one approved speed preset.

- [ ] **Step 4: Add a deterministic evaluation harness**

The CLI accepts `--output-dir` and synthesizes fixed Korean sentences covering product names, brands, numbers, time expressions, units, English/Hangul mixtures, 받침, and 연음. It writes WAV files plus `results.json` containing duration, SHA-256, engine revision, model revision, and manual `pronunciation_status` initialized to `needs_review`.

- [ ] **Step 5: Install and cache the approved model outside Git**

Create a Python 3.12 virtual environment under `G:\Codex\agent-work\ad-creative-studio-tts-cache\venv`. Install MeloTTS at the pinned Git revision and compatible dependencies without changing the main project environment. Download `config.json` and `checkpoint.pth` at model revision `0207e5ad...`, then calculate SHA-256. Store all files under the approved cache root.

- [ ] **Step 6: Run the real pronunciation evaluation**

Run the evaluation CLI with `HF_HOME` and model paths under the approved cache root. Listen to every WAV and update `results.json` with `pass | fail` and notes. If any required sentence fails, do not select MeloTTS as the runtime default and stop before publishing code that claims real TTS readiness.

- [ ] **Step 7: Run focused tests**

Run: `python -m pytest tests/test_tts_provider.py -q`

Expected: all tests pass without loading the real model.

- [ ] **Step 8: Commit**

```bash
git add app/backend/services/tts_provider.py tools/evaluate_korean_tts.py tests/test_tts_provider.py pyproject.toml .env.example .gitignore
git commit -m "feat: add pinned Korean TTS adapter"
```

### Task 3: Three-Image Scene Provider Without Model-Server Changes

**Files:**
- Create: `app/backend/services/scene_images.py`
- Create: `tests/test_scene_images.py`
- Modify: `app/backend/services/model_server_client.py`
- Modify: `app/backend/services/storyboard.py`

**Interfaces:**
- Consumes: `Storyboard`, original product image URL, existing hero image path, output directory.
- Produces: `SceneImageSet(images: tuple[SceneImage, SceneImage, SceneImage], sha256s: tuple[str, ...])`.

- [ ] **Step 1: Write failing provider tests**

Test that the hero image is reused, exactly two extra calls are issued sequentially, prompts differ by `self_aware` and `benefit`, all returned paths remain inside the job directory, and any `product_preserved is not True` fails the whole set.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_scene_images.py -q`

Expected: import failure because the provider does not exist.

- [ ] **Step 3: Add a synchronous scene-generation client boundary**

Reuse the existing origin validation and `/infer` JSON contract. Return response metadata and downloaded RGB bytes; do not add request fields or edit `model_server`.

- [ ] **Step 4: Implement scene prompts and persistence**

Generate two English background prompts from the existing tone/time slot plus fixed purposes. Save sanitized PNG names under the job-owned directory. Reject redirects, non-images, oversized images, failed status, missing preservation confirmation, and fewer than three unique image hashes.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_scene_images.py tests/test_model_to_video_integration.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/backend/services/scene_images.py app/backend/services/model_server_client.py app/backend/services/storyboard.py tests/test_scene_images.py tests/test_model_to_video_integration.py
git commit -m "feat: build three-image Shorts scenes"
```

### Task 4: TTS, Silence, and Caption Renderer

**Files:**
- Modify: `app/backend/services/video_renderer.py`
- Modify: `tests/test_video_renderer.py`
- Create: `tests/test_comic_caption_layout.py`

**Interfaces:**
- Consumes: storyboard, three scene images, sentence WAV files, output MP4 path.
- Produces: `RenderResult` with media metadata, hashes, TTS metadata, and no music fields.

- [ ] **Step 1: Replace music tests with failing comic-render tests**

Verify three distinct images across four scenes, 400~800ms silence around the self-aware beat, no black caption rectangle, maximum two caption lines, product-safe caption placement, one final H.264/AAC MP4, and 10~15 second duration.

- [ ] **Step 2: Run renderer tests and verify failure**

Run: `python -m pytest tests/test_video_renderer.py tests/test_comic_caption_layout.py -q`

Expected: failures because the renderer still accepts `music_path` and one image.

- [ ] **Step 3: Implement caption frames and audio timeline**

Use NanumGothic, bright text, thin stroke, soft shadow, one accent term, and top/bottom safe-area selection. Derive scene length from each WAV plus explicit silence. Reuse the hero image for intro and CTA with a different crop; use the two generated images for self-aware and benefit scenes.

- [ ] **Step 4: Render in one FFmpeg encode where feasible**

Create an explicit concat/filter graph from image loops and sentence WAV/silence inputs. Use argument lists, `libx264`, `yuv420p`, AAC, 1080×1920, 30fps, and the configured preset. Do not accept music or effect inputs.

- [ ] **Step 5: Probe and fail closed**

Reject wrong dimensions, duration, codecs, missing audio, image count/hash mismatch, or output outside `VIDEO_DIR`.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_video_renderer.py tests/test_comic_caption_layout.py -q`

Expected: all selected tests pass with installed FFmpeg/ffprobe.

- [ ] **Step 7: Commit**

```bash
git add app/backend/services/video_renderer.py tests/test_video_renderer.py tests/test_comic_caption_layout.py
git commit -m "feat: render deadpan AI comic Shorts"
```

### Task 5: Workflow, API, Store, and UI Migration

**Files:**
- Modify: `app/backend/schemas/video.py`
- Modify: `app/backend/services/video_workflow.py`
- Modify: `app/backend/api/videos.py`
- Modify: `app/backend/services/store.py`
- Modify: `app/frontend/pages/3_History.py`
- Delete: `app/backend/services/music_catalog.py`
- Delete: `tests/test_music_catalog.py`
- Delete: `assets/music/README.md`
- Delete: `assets/music/manifest.example.json`
- Modify: `tests/test_video_workflow.py`
- Modify: `tests/test_video_api.py`
- Modify: `tests/test_video_store.py`
- Modify: `tests/test_history_video_ui_contract.py`

**Interfaces:**
- Consumes: comic script, three-image set, TTS provider, renderer.
- Produces: queued render, preview, human approval, rush-hour exposure, optional YouTube scheduling.

- [ ] **Step 1: Write failing workflow/API tests**

Assert that approval is blocked by `pronunciation_review_required`, missing TTS hash, fewer than three image hashes, stale source fingerprint, or invalid media. Assert music fields and `allow_silent` are rejected/absent.

- [ ] **Step 2: Add the PM review concurrency regression test**

Start two publish jobs with a blocking fake publisher and assert the second waits, then completes or receives an explicit non-pending terminal status. It must never remain `publish_status=pending` after the worker returns.

- [ ] **Step 3: Run tests and verify failure**

Run: `python -m pytest tests/test_video_workflow.py tests/test_video_api.py tests/test_video_store.py tests/test_history_video_ui_contract.py -q`

Expected: failures against the music schema and non-blocking publish lock.

- [ ] **Step 4: Migrate job schema and workflow**

Remove `music_key`, `music_warning`, `silent_publish_confirmed`, and `allow_silent`. Add `script_version`, `tts_engine`, `tts_voice_preset`, `tts_audio_sha256`, `pronunciation_review_required`, `scene_image_sha256s`, and `caption_layout_version`. Queue render and publish jobs service-wide; preserve optimistic approval concurrency and integrity checks.

- [ ] **Step 5: Update the History UI**

Label the feature `러시아워 무표정 AI 코믹 쇼츠`, show the script and pronunciation review state, preview the MP4, and keep explicit approve/reject/YouTube controls. Remove music warnings and silent-publish controls.

- [ ] **Step 6: Strengthen executable UI coverage**

Extract pure view-state helpers or use Streamlit's test API so tests call behavior with completed, failed, pronunciation-review, approved, and publishing jobs. Remove source-string grep assertions.

- [ ] **Step 7: Run focused tests**

Run: `python -m pytest tests/test_video_workflow.py tests/test_video_api.py tests/test_video_store.py tests/test_history_video_ui_contract.py -q`

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

```bash
git add app/backend/schemas/video.py app/backend/services/video_workflow.py app/backend/api/videos.py app/backend/services/store.py app/frontend/pages/3_History.py tests/test_video_workflow.py tests/test_video_api.py tests/test_video_store.py tests/test_history_video_ui_contract.py
git rm app/backend/services/music_catalog.py tests/test_music_catalog.py assets/music/README.md assets/music/manifest.example.json
git commit -m "feat: switch Shorts workflow to comic TTS"
```

### Task 6: Integration, Documentation, and Serving Boundary

**Files:**
- Modify: `app/backend/main.py`
- Modify: `app/backend/README.md`
- Modify: `SETUP.md`
- Modify: `README.md`
- Modify: `docs/api_contract.md`
- Modify: `docs/integration_checklist.md`
- Modify: `.github/workflows/test.yml`
- Modify: `requirements.txt`
- Modify: `tests/test_api.py`
- Modify: `tests/test_model_to_video_integration.py`
- Modify: `docs/superpowers/plans/2026-08-08-rush-hour-shorts-youtube.md`
- Modify: `docs/superpowers/specs/2026-08-08-rush-hour-shorts-youtube-design.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: documented, runnable, reviewable PR #17 with no model-server diff.

- [ ] **Step 1: Write integration tests for the complete adapter graph**

Use fake model-server and TTS adapters plus real Pillow/FFmpeg fixtures. Create a rush-hour job, render three images and four voiced scenes, inspect the MP4, approve it, and verify exposure. Keep YouTube disabled.

- [ ] **Step 2: Update configuration and docs**

Document external pinned model paths, `--env-file .env`, no implicit model downloads, CPU TTS ownership, service-wide render/publish queues, no music, no automatic upload, and the two extra sequential `/infer` calls per video. Mark the old design and plan as superseded rather than leaving contradictory instructions.

- [ ] **Step 3: Run integration tests**

Run: `python -m pytest tests/test_api.py tests/test_model_to_video_integration.py -q`

Expected: all selected tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/backend/main.py app/backend/README.md SETUP.md README.md docs/api_contract.md docs/integration_checklist.md .github/workflows/test.yml requirements.txt tests/test_api.py tests/test_model_to_video_integration.py docs/superpowers/plans/2026-08-08-rush-hour-shorts-youtube.md docs/superpowers/specs/2026-08-08-rush-hour-shorts-youtube-design.md
git commit -m "docs: hand off comic Shorts operations"
```

### Task 7: Full Verification and Existing Draft PR Update

**Files:**
- Verify all changed files.
- Update: existing GitHub PR #17 title/body; do not open another PR.

**Interfaces:**
- Consumes: complete implementation.
- Produces: pushed Draft PR with fresh checks and explicit PM/serving handoff.

- [ ] **Step 1: Run full local verification**

```bash
python -m pytest -q
python -m ruff check .
python -m compileall -q app model_server tools
python -m pip check
git diff --check origin/main...HEAD
git diff --exit-code origin/main...HEAD -- model_server
git status --short
```

Expected: all tests pass; Ruff, compileall, pip check, and diff check exit zero; `model_server` diff is empty; worktree is clean.

- [ ] **Step 2: Inspect scope and credentials**

Confirm no model weights, WAV, MP4, OAuth token, music asset, `.env`, or cache file is tracked. Confirm only the intended comic-Shorts/design/review changes differ from `origin/main`.

- [ ] **Step 3: Push the existing fork branch**

Run: `git push adam-fork codex/rush-hour-shorts-design`

Expected: branch updates successfully; no force push.

- [ ] **Step 4: Update PR #17 without changing Draft state**

Set the title and body to describe the comic TTS replacement, two extra sequential model calls, unchanged `/infer` contract, removed music path, actual TTS validation status, PM review fixes, exact verification commands, and remaining UI/operational approvals.

- [ ] **Step 5: Verify remote checks**

Run: `gh pr checks 17 --repo codeit-part4-team2/ad-creative-studio --watch`

Expected: all required checks pass. If a check fails, inspect the log and fix only the root cause before pushing again.

