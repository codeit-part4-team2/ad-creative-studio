# PR #22 Review Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve PR #22 review items 1-7, 9, and 10 without changing the approved TTS, `/infer`, YouTube approval, or final-video contracts; document item 8 as a retention-policy follow-up.

**Architecture:** Keep captions readable by preserving word wrapping for normal copy and applying a deterministic two-line ellipsis fallback only when text cannot fit. Move negative-prompt safety vocabulary into one neutral module, deduplicate it before model inference, and keep the most important text/background exclusions first. Harden the video workflow at state, runtime, recovery, and async API boundaries while retaining the single-worker deployment contract.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, Pillow, Diffusers/SDXL, pytest, Ruff, GitHub Actions.

## Global Constraints

- Preserve the four-scene `deadpan-ai-v2` script and full spoken TTS text.
- Keep captions to at most two lines inside the existing 900x210 safe area.
- Do not add OCR, a new model call, a new dependency, or a YouTube auto-publish bypass.
- Runtime validation for TTS and FFmpeg must finish before either L4 `/infer` request.
- Invalid persisted jobs must fail closed for duplicate-render prevention and emit an operator-visible log.
- Completed work-directory retention remains unchanged until the team chooses a retention period.

---

### Task 1: Long Caption Fallback

**Files:**
- Modify: `tests/test_comic_caption_layout.py`
- Modify: `app/backend/services/video_renderer.py`

**Interfaces:**
- Consumes: `_font_and_lines(draw, text, font_path, max_width, max_height)`.
- Produces: at most two width-safe lines; overlong captions end in `…` while the storyboard spoken text remains untouched.

- [ ] Add a regression test using the exact long product sentence from the review and assert two lines, an ellipsis, and width compliance.
- [ ] Run the focused test and verify the existing implementation raises `ValueError`.
- [ ] Add a two-line ellipsis fallback at the minimum approved font size without changing normal word wrapping.
- [ ] Run caption-layout and renderer tests and verify they pass.
- [ ] Commit the isolated caption fix.

### Task 2: Prompt Safety Deduplication and Budget

**Files:**
- Create: `app/prompt/safety.py`
- Modify: `app/prompt/builder.py`
- Modify: `app/backend/services/scene_images.py`
- Modify: `model_server/pipelines.py`
- Modify: `tests/test_prompt_builder.py`
- Modify: `tests/test_scene_images.py`
- Modify: `tests/test_model_server_pipelines.py`

**Interfaces:**
- Produces: `DEFAULT_NEGATIVE_PROMPT`, `FAST_BACKGROUND_NEGATIVE_PROMPT`, and `merge_negative_prompts(*prompts)` with stable ordering and case-insensitive exact-term deduplication.
- Consumes: existing comma-separated negative-prompt strings at the backend/model-server boundary.

- [ ] Add failing tests proving the fast path contains no duplicate terms, keeps text/sign/background exclusions, and remains under the conservative 28-term safety budget.
- [ ] Run the three focused prompt suites and verify the duplicated 57-term prompt fails.
- [ ] Introduce the shared prompt-safety module and import it from all three paths.
- [ ] Put text-free instructions at the beginning of the fast background positive prompt so truncation cannot discard them first.
- [ ] Run focused prompt/model pipeline tests and commit.

### Task 3: Fail-Closed Persisted Job Index

**Files:**
- Modify: `tests/test_video_workflow.py`
- Modify: `app/backend/services/video_workflow.py`

**Interfaces:**
- Consumes: raw `store.VIDEO_JOBS` records during `VideoWorkflowService` initialization.
- Produces: conservative active-result reservations for malformed records that still expose string `result_id` and `video_job_id`, plus an error log.

- [ ] Add a failing test with a malformed completed record and assert a second job for the same result is blocked and logged.
- [ ] Run the test and verify duplicate creation currently succeeds.
- [ ] Reserve the raw result ID on validation failure and log the validation exception without sensitive record contents.
- [ ] Run workflow tests and commit.

### Task 4: Non-Blocking Create Cleanup

**Files:**
- Modify: `tests/test_video_api.py`
- Modify: `app/backend/api/videos.py`

**Interfaces:**
- Consumes: synchronous `VideoWorkflowService.create(result_id)` which can perform filesystem cleanup.
- Produces: a synchronous FastAPI route executed by Starlette's worker threadpool, preserving the same HTTP response contract.

- [ ] Add a concurrent API regression test where a deliberately slow create call must not delay an unrelated health request.
- [ ] Run the test and verify the current async route blocks the app event loop.
- [ ] Convert only the create endpoint to a synchronous route so FastAPI offloads it automatically.
- [ ] Run video API tests and commit.

### Task 5: Render and Publish Retry State Safety

**Files:**
- Modify: `tests/test_video_workflow.py`
- Modify: `app/backend/services/video_workflow.py`

**Interfaces:**
- `run_render(video_job_id)` ignores only terminal `COMPLETED`/`FAILED`; `PROCESSING` raises `WorkflowConflict`.
- `run_publish(video_job_id)` returns unchanged for terminal publish states and invokes the publisher at most once.

- [ ] Add failing tests for a `PROCESSING` render retry and a second publish call after scheduling.
- [ ] Run both tests and verify the first is silently swallowed and the second raises.
- [ ] Narrow the render terminal-state guard and add the publish terminal-state guard.
- [ ] Run workflow and video API tests and commit.

### Task 6: Recovery Timestamp and Renderer Runtime Gate

**Files:**
- Modify: `tests/test_video_store.py`
- Modify: `tests/test_video_renderer.py`
- Modify: `tests/test_video_workflow.py`
- Modify: test renderer doubles in video-related test files
- Modify: `app/backend/services/store.py`
- Modify: `app/backend/services/video_renderer.py`
- Modify: `app/backend/services/video_workflow.py`

**Interfaces:**
- `_recover_video_jobs(*, recovered_at=None)` stamps interrupted render failures with an aware recovery time.
- `RushHourVideoRenderer.validate_runtime()` verifies the font and both FFmpeg executables.
- `run_render()` calls both TTS and renderer runtime validators before scene generation.

- [ ] Add failing timestamp, missing-executable, and pre-L4 renderer-validation tests.
- [ ] Run them and verify the old timestamp and late executable failures.
- [ ] Implement aware recovery timestamps and the renderer runtime validator with sanitized errors.
- [ ] Update typed test doubles to implement `validate_runtime()` and call the validator before scene generation.
- [ ] Run store, renderer, workflow, API, and model-to-video tests and commit.

### Task 7: Follow-up Documentation and Full Verification

**Files:**
- Modify: `docs/integration_checklist.md`
- Modify: `docs/superpowers/plans/2026-08-13-pr22-review-round2.md`

**Interfaces:**
- Documents that completed intermediate work directories require an explicit retention period before automated deletion.

- [ ] Record item 8 as a non-blocking storage-retention decision with final MP4 excluded from intermediate cleanup.
- [ ] Run all pytest tests, Ruff, `git diff --check`, and the real FFmpeg render integration.
- [ ] Inspect git diff and confirm no TTS/model/approval contract drift.
- [ ] Push the existing branch, wait for GitHub Actions, and comment on PR #22 with item-by-item evidence.

