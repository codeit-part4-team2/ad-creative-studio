# Shorts TTS Headroom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover enough 15-second headroom by shortening only the static self-aware and CTA copy that consumed 8.036 seconds in the second L4 E2E run.

**Architecture:** Keep the PR #26 renderer and MeloTTS configuration unchanged. Replace all four deterministic self-aware/CTA template pairs, increment the script contract to `deadpan-ai-v4`, and verify the user-visible copy at the `build_comic_script` and storyboard boundaries.

**Tech Stack:** Python 3.11+, dataclasses, hashlib, pytest

## Global Constraints

- Preserve the four scenes in `INTRO`, `SELF_AWARE`, `BENEFIT`, `CTA` order.
- Keep MeloTTS speed `0.94`, pronunciation lexicon, render silence, and `9.95~15.05` duration bounds unchanged.
- Change only static self-aware and CTA text; preserve product name and first selling point text.
- Record the changed copy contract as `deadpan-ai-v4`.
- Do not claim real duration success until L4 MeloTTS E2E passes.

---

### Task 1: Cover all concise copy variants with failing tests

**Files:**
- Modify: `tests/test_comic_script.py`
- Modify: `tests/test_storyboard.py`

**Interfaces:**
- Consumes: `build_comic_script(...) -> ComicScript` and `build_storyboard(...) -> Storyboard`.
- Produces: behavior tests for all four deterministic self-aware/CTA template pairs and the v4 fingerprint boundary.

- [ ] **Step 1: Change the representative expected contract**

```python
assert first.version == "deadpan-ai-v4"
assert self_aware.display_text == "광고입니다."
assert first.lines[-1].display_text == "보세요. 전 일합니다."
```

- [ ] **Step 2: Add table-driven coverage of all four template pairs**

Use literal product/time-slot fixtures whose stable hash selects each variant:

```python
(
    ("휴대용 선풍기", "commute_am", "광고입니다.", "보세요. 전 일합니다."),
    ("공기청정기", "commute_am", "안 쉽니다. 광고합니다.", "보세요. 안 늦습니다."),
    ("전자레인지", "commute_pm", "퇴근은 없습니다.", "보세요. 전 못 갑니다."),
    ("휴대용 선풍기", "commute_pm", "광고입니다. 최선입니다.", "보세요. 전 일합니다."),
)
```

For every built script, assert the literal self-aware and CTA values and preserve the existing benefit/fact assertions.

- [ ] **Step 3: Verify RED**

Run: `python -m pytest tests/test_comic_script.py tests/test_storyboard.py -q`

Expected: failures because main still returns `deadpan-ai-v3` and the longer v3 text.

### Task 2: Implement `deadpan-ai-v4`

**Files:**
- Modify: `app/backend/services/comic_script.py`

**Interfaces:**
- Produces: the same `build_comic_script` API with `SCRIPT_VERSION = "deadpan-ai-v4"` and the four approved static copy pairs.

- [ ] **Step 1: Replace only the static template fields**

Keep every `intro` value intact. Replace `self_aware` and `cta` with the exact table in the design. Do not change `build_comic_script`, selling-point formatting, lexicon handling, or selection hashing.

- [ ] **Step 2: Verify GREEN**

Run: `python -m pytest tests/test_comic_script.py tests/test_storyboard.py -q`

Expected: all focused tests pass.

- [ ] **Step 3: Run dependent workflow tests**

Run:

```powershell
python -m pytest tests/test_model_to_video_integration.py tests/test_video_workflow.py tests/test_video_api.py tests/test_api.py -q
```

Expected: all API and video workflow contracts pass without renderer changes.

### Task 3: Full verification, continuity, and Draft PR

**Files:**
- Modify: `.codex/project-ledger/PROJECT_STATE.md`
- Modify: `.codex/project-ledger/DECISIONS.md`
- Modify: `.codex/project-ledger/NEXT_STEPS.md`
- Modify: `.codex/project-ledger/KNOWN_ISSUES.md`
- Modify: `.codex/project-ledger/BUILD_EVIDENCE.md`

**Interfaces:**
- Produces: a clean pushed `codex/shorts-tts-headroom` branch and Draft PR against `main`.

- [ ] **Step 1: Run the full gate**

```powershell
python -m pytest -q
python -m ruff check app/backend/services/comic_script.py tests/test_comic_script.py tests/test_storyboard.py
python -m compileall -q app tests
python -m pip check
git diff --check
```

- [ ] **Step 2: Record evidence and validate the ledger**

Record the PR #26 merge commit, second L4 measurements, RED/GREEN results, and remaining E2E gate. Run:

```powershell
python "$env:USERPROFILE\.codex\skills\project-continuity-ledger\scripts\ledger.py" check . --json
```

- [ ] **Step 3: Commit and publish**

Stage only the design/plan, copy implementation, copy tests, and ledger files. Push the branch and open a Draft PR against `main` with the exact L4 measurements and remaining human verification.
