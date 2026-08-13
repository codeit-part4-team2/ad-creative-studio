# Shorts Duration Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep rush-hour Shorts within 10~15 seconds without unnatural TTS speed-up and make duration failures directly diagnosable.

**Architecture:** Shorten the deterministic four-line copy contract to `deadpan-ai-v3`. Add one immutable segment-timing calculation used by both pre-render validation and FFmpeg assembly, padding short speech to storyboard targets while rejecting genuine overruns with a numeric breakdown.

**Tech Stack:** Python 3.11+, dataclasses, Pillow, FFmpeg/ffprobe, pytest

## Global Constraints

- Preserve `INTRO`, `SELF_AWARE`, `BENEFIT`, and `CTA` in that order.
- Use only the stored product name and first stored selling point.
- Keep MeloTTS speed `0.94`, pronunciation lexicon, and voice preset unchanged.
- Keep the accepted video range at `9.95~15.05` seconds.
- Do not truncate speech, loosen the duration contract, or add a second TTS pass.
- Treat L4 MeloTTS E2E as external acceptance evidence, not a local test result.

---

### Task 1: Concise `deadpan-ai-v3` copy

**Files:**
- Modify: `tests/test_comic_script.py`
- Modify: `tests/test_storyboard.py`
- Modify: `app/backend/services/comic_script.py`

**Interfaces:**
- Consumes: `build_comic_script(...) -> ComicScript`
- Produces: the same deterministic API with `ComicScript.version == "deadpan-ai-v3"` and shorter display/spoken text.

- [ ] **Step 1: Write the failing copy-contract tests**

Change the morning fixture expectations and add a bounded fixture assertion:

```python
assert first.version == "deadpan-ai-v3"
assert first.lines[0].display_text == "휴대용 선풍기, 나왔습니다."
assert self_aware.display_text == "광고입니다. 저도 압니다."
assert first.lines[-1].display_text == "보세요. 저는 안 쉽니다."
assert sum(len(line.spoken_text) for line in first.lines) <= 64
```

Keep the existing first-selling-point and pronunciation assertions, changing the benefit to
`"USB-C 충전, 됩니다."` / `"유에스비 씨 충전, 됩니다."`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_comic_script.py tests/test_storyboard.py -q`

Expected: failures on `deadpan-ai-v2` and the longer copy.

- [ ] **Step 3: Implement the concise template bank**

Set `SCRIPT_VERSION = "deadpan-ai-v3"`, retain stable template selection, and use these concise responsibilities:

```python
intro = "{product}, 나왔습니다."
self_aware = "광고입니다. 저도 압니다."
benefit = f"{selling_point}, 됩니다."
cta = "보세요. 저는 안 쉽니다."
```

The alternate templates remain time-slot specific and equally concise.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_comic_script.py tests/test_storyboard.py -q`

Expected: all focused tests pass.

### Task 2: Shared scene timing and numeric failure evidence

**Files:**
- Modify: `tests/test_video_renderer.py`
- Modify: `app/backend/services/video_renderer.py`

**Interfaces:**
- Produces: `_SegmentTiming(segment_duration_sec, pre_silence_sec, post_silence_sec)`.
- Produces: `_segment_timing(scene: StoryboardScene, speech_duration_sec: float) -> _SegmentTiming`.
- Changes: `_write_segment(...)` consumes explicit pre/post silence computed by that helper.

- [ ] **Step 1: Write failing timing tests**

Add a real helper test proving a 0.1-second voice in a 3-second benefit scene becomes exactly
3 seconds with 0.1-second pre-roll and 2.8-second post-roll. Change the FFmpeg integration
storyboard to production targets `(2.5, 2.5, 3.0, 3.0)` and expect about 11.6 seconds.

- [ ] **Step 2: Add the measured overrun regression**

Build four `TTSAudio` values with durations `(4.186, 6.016, 5.633, 6.527)` and assert the
pre-render error contains `estimated=23.962s`, `speech_total=22.362s`,
`silence_total=1.600s`, and all four scene labels. Assert `_run` remains uncalled.

- [ ] **Step 3: Verify RED**

Run: `python -m pytest tests/test_video_renderer.py -q`

Expected: the helper is missing, the integration remains near 10 seconds, and the current
generic error lacks the numeric breakdown.

- [ ] **Step 4: Implement one timing source**

Create the frozen timing dataclass and helper using:

```python
minimum_silence = _scene_silence_sec(scene)
segment_duration = max(
    scene.duration_sec,
    speech_duration_sec + 2 * minimum_silence,
)
pre_silence = minimum_silence
post_silence = segment_duration - speech_duration_sec - pre_silence
```

Build the tuple once in `render`, validate its sum, and pass its values to `_write_segment`.
Include total and per-scene seconds in an overrun exception.

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_video_renderer.py -q`

Expected: timing, measured-overrun, runtime validation, caption, and real FFmpeg tests pass.

### Task 3: Full gate, continuity, and Draft PR

**Files:**
- Modify: `.codex/project-ledger/PROJECT_STATE.md`
- Modify: `.codex/project-ledger/DECISIONS.md`
- Modify: `.codex/project-ledger/NEXT_STEPS.md`
- Modify: `.codex/project-ledger/KNOWN_ISSUES.md`
- Modify: `.codex/project-ledger/BUILD_EVIDENCE.md`

**Interfaces:**
- Produces: a pushed `codex/shorts-duration-budget` branch and Draft PR against `main`.

- [ ] **Step 1: Run focused and full validation**

```powershell
python -m pytest tests/test_comic_script.py tests/test_storyboard.py tests/test_video_renderer.py -q
python -m pytest -q
python -m ruff check app/backend/services/comic_script.py app/backend/services/video_renderer.py tests/test_comic_script.py tests/test_storyboard.py tests/test_video_renderer.py
python -m compileall -q app tests
git diff --check
```

- [ ] **Step 2: Update and validate the continuity ledger**

Record the branch/base, exact commands and results, confirmed root cause, and the remaining L4
MeloTTS E2E gate. Run:

```powershell
python "$env:USERPROFILE\.codex\skills\project-continuity-ledger\scripts\ledger.py" check . --json
```

- [ ] **Step 3: Commit and push only intended files**

Review `git status -sb` and `git diff`, stage explicit paths, commit with
`fix: keep rush-hour shorts within duration budget`, and push the current branch.

- [ ] **Step 4: Open a Draft PR**

Create a Draft PR against `main` describing the root cause, copy/timing changes, local evidence,
and the external VM E2E acceptance gate.
