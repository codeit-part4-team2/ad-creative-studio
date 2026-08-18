# PR #28 Review Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the reproducible PR #28 review issues without adding model inference or weakening the clean-source and full-bleed contracts.

**Architecture:** Generation preparation will centralize copy/source work, save clean sources only for rush-hour results, and run independent blocking work concurrently. The mock path will keep per-format placeholders for formatted cards. The UI will hide legacy Shorts actions and explain regeneration, while real crop/readability risks remain explicit VM E2E gates rather than speculative image heuristics.

**Tech Stack:** Python 3.11+, asyncio, Pillow, Pydantic, Streamlit, pytest.

## Global Constraints

- No new model inference, dependency, environment variable, or L4 configuration.
- Preserve `source_image_url` as the only Shorts hero input and fail closed in the backend.
- Preserve boxless, shadowless full-bleed captions.
- Work locally only; do not stage, commit, push, or open a PR without a new user instruction.

---

### Task 1: Restore mock formatted-image behavior

**Files:**
- Modify: `app/backend/services/generation_service.py`
- Test: `tests/test_generation_service.py`

**Interfaces:**
- Consumes: `overlay.generate_and_save(..., background_image=None)`
- Produces: formatted mock exports whose corners use the requested tone color at every aspect ratio

- [x] Add a failing LocalOverlayGenerationService test for `sns_card` and `detail_banner` corner colors.
- [x] Run the focused test and confirm white-letterbox failure.
- [x] Stop passing the square clean-source placeholder into formatted mock exports.
- [x] Run the focused test to GREEN.

### Task 2: Bound clean-source storage and parallelize preparation

**Files:**
- Modify: `app/backend/services/generation_service.py`
- Modify: `tests/test_model_server_generation.py`
- Test: `tests/test_generation_service.py`

**Interfaces:**
- Produces: `_prepare_copy_and_source(...) -> tuple[str, str, str | None]`
- Contract: only `commute_am` and `commute_pm` receive `source_image_url`

- [x] Add failing tests proving normal slots do not persist a source and rush-hour slots do.
- [x] Add a failing synchronization test proving source persistence and copy generation overlap.
- [x] Run focused tests and record expected failures.
- [x] Implement one shared async helper using `asyncio.gather` only when a rush-hour source is required.
- [x] Reuse the helper from mock and model-server services and normalize `time_slot` once per item.
- [x] Run focused tests to GREEN.

### Task 3: Make legacy-result UX explicit and normalize source URLs

**Files:**
- Modify: `app/backend/services/storyboard.py`
- Modify: `app/frontend/video_view_state.py`
- Modify: `app/frontend/pages/3_History.py`
- Modify: `tests/test_storyboard.py`
- Modify: `tests/test_history_video_ui_contract.py`

**Interfaces:**
- Produces: `short_creation_unavailable_reason(result) -> str | None`
- Contract: whitespace around a valid source URL is stripped; missing legacy source shows regeneration guidance and no create button

- [x] Add failing tests for whitespace normalization and legacy UI blocking reason.
- [x] Run focused tests and confirm failures.
- [x] Normalize the backend URL before prefix/path validation.
- [x] Require a clean source in `can_create_rush_hour_short` and render the regeneration message for eligible legacy results.
- [x] Run focused tests to GREEN.

### Task 4: Preserve external visual acceptance gates

**Files:**
- Modify: `docs/integration_checklist.md`
- Modify: `.codex/project-ledger/BUILD_EVIDENCE.md`
- Modify: `.codex/project-ledger/DECISIONS.md`
- Modify: `.codex/project-ledger/NEXT_STEPS.md`
- Modify: `.codex/project-ledger/PROJECT_STATE.md`

**Interfaces:**
- Produces: role-specific VM checks for four-scene crop safety, complex-background caption readability, and legacy regeneration behavior

- [x] Record why automatic focal cropping is not introduced without segmentation/saliency evidence.
- [x] Add exact server/UI acceptance steps using newly generated rush-hour advertisements.
- [x] Record RED/GREEN and full-suite evidence after verification.

### Task 5: Full verification

**Files:**
- Verify all changed production, test, documentation, and ledger files.

- [x] Run focused generation, storyboard, and UI tests.
- [x] Run dependent API/video workflow tests.
- [x] Run `python -m pytest -q`.
- [x] Run changed-file Ruff, compileall, ledger check, and `git diff --check`.
- [x] Confirm no files are staged and no remote state changed.
