# Final Pre-Push Model and Shorts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the final safe model-server improvements, retain the reviewed Shorts generator, and leave separate model, Shorts, and combined branches as clean local commits immediately before push.

**Architecture:** Reuse the existing model branch for model-only changes and the existing Shorts worktree for video-only changes. Cherry-pick the finished model commit into the existing local integration branch, then verify the combined contract without pushing any branch.

**Tech Stack:** Python 3.11+, PyTorch/Diffusers, FastAPI, Pydantic 2, Pillow, FFmpeg, Streamlit, pytest, Ruff, Git worktrees.

## Global Constraints

- Keep `fast_composite` at 768x768 background, 1024x1024 final output, and 4 steps by default.
- Keep `quality_regenerate` at 1024x1024 and 30 steps.
- Keep Uvicorn at one worker per L4 and preserve serialized GPU generation.
- Do not download model weights or dependencies larger than 100 MB locally.
- Do not change Shorts approval, rush-hour exposure, music licensing, or YouTube opt-in behavior.
- Do not push, update a PR, merge remote branches, deploy, or publish to YouTube.
- Every production behavior begins with a focused failing test.

---

### Task 1: Use the FP16-Safe VAE in the Fast Profile

**Files:**
- Modify: `tests/test_model_server_pipelines.py`
- Modify: `model_server/pipelines.py`

**Interfaces:**
- Consumes: `AutoencoderKL.from_pretrained(model_id, torch_dtype=dtype, use_safetensors=True)`.
- Produces: both SDXL pipeline constructors receive the explicit `vae` instance.

- [ ] **Step 1: Add a failing loader test**

Inject fake `torch` and `diffusers` modules, load the fast profile, and assert
that `StableDiffusionXLPipeline.from_pretrained` receives the exact object
returned by `AutoencoderKL.from_pretrained` under the `vae` keyword.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_model_server_pipelines.py::test_fast_loader_uses_fp16_safe_vae -q`

Expected: FAIL because the fast constructor currently receives no `vae`.

- [ ] **Step 3: Implement the shared VAE load**

Load `madebyollin/sdxl-vae-fp16-fix` before the profile branch and pass it to
both `StableDiffusionXLPipeline` and
`StableDiffusionXLControlNetPipeline`. Remove the duplicate quality-only load.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_model_server_pipelines.py -q`

Expected: all pipeline tests pass.

### Task 2: Report GPU Queue Wait Separately

**Files:**
- Modify: `tests/test_model_server_inference_runtime.py`
- Modify: `tests/test_model_server_api_runtime.py`
- Modify: `tests/test_model_server_benchmark_latency.py`
- Modify: `model_server/inference.py`
- Modify: `model_server/schemas.py`

**Interfaces:**
- Produces: `InferenceResult.gpu_queue_wait_sec: float | None`.
- Produces: `InferResponse.gpu_queue_wait_sec: float | None`.
- Produces: `stage_times_sec["gpu_queue_wait"]` on successful inference.

- [ ] **Step 1: Add failing runtime and API tests**

Hold `InferenceEngine._gpu_lock`, start a request in another thread, release
the lock after at least 50 milliseconds, and assert the result reports
`gpu_queue_wait_sec >= 0.04`. Assert API serialization preserves the field.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_model_server_inference_runtime.py tests/test_model_server_api_runtime.py -q`

Expected: FAIL because the field and stage do not exist.

- [ ] **Step 3: Implement timed lock acquisition**

Measure `time.perf_counter()` immediately before and after
`self._gpu_lock.acquire()`, release the lock in `finally`, add the rounded value
to stage metadata, and set the top-level result field. Do not include CUDA
synchronization in queue timing.

- [ ] **Step 4: Add benchmark coverage**

Extend the literal benchmark fixture with `gpu_queue_wait` and assert its
median appears in `stage_median_sec` while configuration output remains
unchanged.

- [ ] **Step 5: Verify GREEN**

Run: `python -m pytest tests/test_model_server_inference_runtime.py tests/test_model_server_api_runtime.py tests/test_model_server_benchmark_latency.py -q`

Expected: all focused tests pass.

### Task 3: Record the External L4 Evidence and Local Gate

**Files:**
- Modify: `model_server/README.md`
- Modify: `docs/L4_BENCHMARK_CHECKLIST.md`
- Modify: `docs/model_server_handoff.md`
- Modify: `.codex/project-ledger/PROJECT_STATE.md`
- Modify: `.codex/project-ledger/DECISIONS.md`
- Modify: `.codex/project-ledger/NEXT_STEPS.md`
- Modify: `.codex/project-ledger/KNOWN_ISSUES.md`
- Modify: `.codex/project-ledger/BUILD_EVIDENCE.md`

**Interfaces:**
- Produces: evidence-safe handoff that distinguishes local verification from the serving owner's external report.

- [ ] **Step 1: Document the selected default and warnings**

Record 4 steps as the selected fast default, explain queue timing, and record
the VAE same-seed comparison as the remaining external gate.

- [ ] **Step 2: Run the model branch gate**

Run:

```text
python -m pytest -q
python -m ruff check app model_server tests tools scripts
python -m compileall -q app model_server tests tools scripts
python -m pip check
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 3: Update and validate the ledger**

Record the exact branch head, commands, counts, and unresolved L4 checks. Run:

`python "$env:USERPROFILE/.codex/skills/project-continuity-ledger/scripts/ledger.py" check . --json`

- [ ] **Step 4: Commit model-only changes locally**

Stage only the reviewed model source, tests, docs, and ledger. Commit without
pushing.

### Task 4: Reverify Shorts and the Combined Branch

**Files:**
- Preserve: existing `codex/rush-hour-shorts-design` source and tests.
- Update by cherry-pick: existing `codex/model-shorts-integration` worktree.

**Interfaces:**
- Consumes: the reviewed model-only commit and existing Shorts commits.
- Produces: a clean combined local branch with no external publication.

- [ ] **Step 1: Run the complete Shorts gate**

Run pytest, Ruff, compileall, `pip check`, `git diff --check`, credential scan,
and ignored-artifact checks in the Shorts worktree.

- [ ] **Step 2: Cherry-pick the model-only commit into integration**

Apply the new model commits in order. Resolve only genuine overlap while
preserving both dependency groups and both environment contracts.

- [ ] **Step 3: Run the combined gate**

Run pytest, Ruff, compileall, `pip check`, `git diff --check`, credential scan,
and ignored-artifact checks in the integration worktree.

- [ ] **Step 4: Preserve the pre-push state**

Confirm all three branches are clean, no listeners remain on ports 8000, 8001,
8010, 8501, or 8511, and no remote ref changed.
