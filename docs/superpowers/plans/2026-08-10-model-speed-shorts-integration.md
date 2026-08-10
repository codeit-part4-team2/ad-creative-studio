# Model Speed and Shorts Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the model-server dependency contract, generate only the fast SDXL background at 768x768 while preserving 1024x1024 output, and prove that persisted model results feed the reviewed rush-hour Shorts workflow.

**Architecture:** Keep PR #15 focused on model serving and keep the Shorts implementation on its existing branch. Verify each branch independently, then create an unpushed local integration branch from the model branch and combine the verified Shorts commit for end-to-end regression testing.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, PyTorch/Diffusers configuration, Pillow, FFmpeg, Streamlit, pytest, Ruff, Git worktrees.

## Global Constraints

- Generate only `fast_composite` backgrounds at 768x768 by default.
- Keep `quality_regenerate` generation, final ad output, and the product canvas at 1024x1024.
- Keep `FAST_BACKGROUND_SIZE=1024` as a rollback and benchmark option.
- Use `numpy==2.3.5` with `rembg[gpu]==2.0.76` and Python 3.11 or newer.
- Do not download model weights or dependencies larger than 100 MB without separate user confirmation.
- Do not change the base model, LoRA, ControlNet, IP-Adapter, or rembg model.
- Do not enable TF32 or `torch.compile` by default; benchmark them independently on L4.
- Do not add TTS, narration, unlicensed music, or automatic YouTube publishing.
- Keep generated images, videos, logs, OAuth data, and model weights out of Git.
- Do not push, update PR #15, open a Shorts PR, or merge remote branches in this plan.
- Every new behavior begins with a focused failing test.

---

### Task 1: Enforce Compatible Exact Model Dependencies

**Files:**
- Modify: `tests/test_model_server_requirements.py`
- Modify: `model_server/requirements.txt`

**Interfaces:**
- Consumes: `[project.optional-dependencies].model` from `pyproject.toml` and exact model-server pins.
- Produces: a regression test proving every overlapping exact pin satisfies the project model constraint.

- [ ] **Step 1: Add a failing semantic compatibility test**

```python
import tomllib
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


def test_model_server_pins_satisfy_project_model_constraints() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    model_constraints = {
        canonicalize_name(req.name): req
        for raw in project["project"]["optional-dependencies"]["model"]
        for req in [Requirement(raw)]
    }
    exact_pins = {
        canonicalize_name(req.name): req
        for raw in _requirement_lines(Path("model_server/requirements.txt"))
        for req in [Requirement(raw)]
    }

    for name, constraint in model_constraints.items():
        if name not in exact_pins:
            continue
        pin = exact_pins[name]
        pinned_version = next(
            Version(item.version)
            for item in pin.specifier
            if item.operator == "=="
        )
        assert pinned_version in constraint.specifier, (
            f"{pin} does not satisfy project constraint {constraint}"
        )
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest tests/test_model_server_requirements.py -q`

Expected: FAIL because `numpy==2.2.6` does not satisfy `numpy>=2.3,<3`.

- [ ] **Step 3: Pin the compatible NumPy release**

Change the exact line to:

```text
numpy==2.3.5
```

- [ ] **Step 4: Run focused dependency tests and verify GREEN**

Run: `python -m pytest tests/test_model_server_requirements.py -q`

Expected: both exact-pin syntax and semantic-compatibility tests pass.

- [ ] **Step 5: Commit the dependency repair locally**

```bash
git add model_server/requirements.txt tests/test_model_server_requirements.py
git commit -m "fix: align model server dependency pins"
```

---

### Task 2: Generate the Fast Background at 768 and Normalize to 1024

**Files:**
- Modify: `model_server/config.py`
- Modify: `model_server/pipelines.py`
- Modify: `tests/test_model_server_config.py`
- Modify: `tests/test_model_server_pipelines.py`

**Interfaces:**
- Produces: `InferenceConfig.fast_background_size: int` from `FAST_BACKGROUND_SIZE`.
- Produces: a `GenerationResult.image` normalized to `image_size` before composition.

- [ ] **Step 1: Add failing configuration tests**

```python
def test_fast_background_defaults_to_768_for_1024_output() -> None:
    config = InferenceConfig.from_env({})
    assert config.fast_background_size == 768
    assert config.image_size == 1024


@pytest.mark.parametrize("value", ["0", "770", "1032"])
def test_fast_background_size_must_be_positive_aligned_and_not_larger(value: str) -> None:
    with pytest.raises(ValueError, match="FAST_BACKGROUND_SIZE"):
        InferenceConfig.from_env({"FAST_BACKGROUND_SIZE": value})
```

- [ ] **Step 2: Run config tests and verify RED**

Run: `python -m pytest tests/test_model_server_config.py -q`

Expected: FAIL because `fast_background_size` is absent.

- [ ] **Step 3: Implement configuration parsing**

Add `fast_background_size: int = 768`, parse `FAST_BACKGROUND_SIZE`, require
divisibility by 8, and reject values greater than `IMAGE_SIZE`.

- [ ] **Step 4: Run config tests and verify GREEN**

Run: `python -m pytest tests/test_model_server_config.py -q`

Expected: PASS.

- [ ] **Step 5: Add failing pipeline behavior tests**

Configure the fake fast pipeline with `image_size=16` and
`fast_background_size=8`, then assert:

```python
assert fake.calls[0]["width"] == 8
assert fake.calls[0]["height"] == 8
assert result.image.size == (16, 16)
```

For the quality profile, assert width and height remain 16.

- [ ] **Step 6: Run pipeline tests and verify RED**

Run: `python -m pytest tests/test_model_server_pipelines.py -q`

Expected: FAIL because fast generation still uses `image_size` directly.

- [ ] **Step 7: Implement fast-only background normalization**

Call the fast pipeline with `fast_background_size`; after reading
`output.images[0]`, resize only fast output to `(image_size, image_size)` with
`Image.Resampling.LANCZOS`. Keep quality generation unchanged.

- [ ] **Step 8: Run pipeline and compositor regression tests**

Run: `python -m pytest tests/test_model_server_pipelines.py tests/test_model_server_compositing.py tests/test_model_server_inference_runtime.py -q`

Expected: PASS.

- [ ] **Step 9: Commit the fast background behavior locally**

```bash
git add model_server/config.py model_server/pipelines.py tests/test_model_server_config.py tests/test_model_server_pipelines.py
git commit -m "perf: lower fast background generation resolution"
```

---

### Task 3: Report Resolution in API and Benchmark Evidence

**Files:**
- Modify: `model_server/pipelines.py`
- Modify: `model_server/inference.py`
- Modify: `model_server/schemas.py`
- Modify: `tools/benchmark_latency.py`
- Modify: `tests/test_model_server_inference_runtime.py`
- Modify: `tests/test_model_server_api_runtime.py`
- Modify: `tests/test_model_server_benchmark_latency.py`

**Interfaces:**
- Produces: `background_size` and `output_size` integer fields in successful `/infer` responses.
- Produces: benchmark `configuration` containing profile, steps, background size, and output size.

- [ ] **Step 1: Add failing inference metadata assertions**

Extend the fast inference test to assert:

```python
assert result.background_size == 768
assert result.output_size == 1024
```

Extend the API test so serialized responses include the same fields.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_model_server_inference_runtime.py tests/test_model_server_api_runtime.py -q`

Expected: FAIL because the fields do not exist.

- [ ] **Step 3: Thread explicit size metadata through the result models**

Add the two fields to `GenerationResult`, `InferenceResult`, and `InferResponse`.
Set fast `background_size=fast_background_size`; set quality
`background_size=image_size`; always set `output_size=image_size`.

- [ ] **Step 4: Run inference and API tests and verify GREEN**

Run: `python -m pytest tests/test_model_server_inference_runtime.py tests/test_model_server_api_runtime.py -q`

Expected: PASS.

- [ ] **Step 5: Add a failing benchmark configuration test**

Create successful runs with identical metadata and assert:

```python
assert summary["configuration"] == {
    "model_profile": "fast_composite",
    "num_inference_steps": 4,
    "background_size": 768,
    "output_size": 1024,
}
```

Also assert mixed configurations raise `ValueError`.

- [ ] **Step 6: Run benchmark tests and verify RED**

Run: `python -m pytest tests/test_model_server_benchmark_latency.py -q`

Expected: FAIL because `summarize_runs` omits configuration.

- [ ] **Step 7: Implement consistent benchmark configuration reporting**

Extract the four metadata keys from every run, require one unique tuple, and
return it under `configuration` beside latency and stage medians.

- [ ] **Step 8: Run all model-server focused tests**

Run: `python -m pytest tests/test_model_server_*.py -q`

Expected: PASS.

- [ ] **Step 9: Commit metadata and benchmark evidence locally**

```bash
git add model_server/pipelines.py model_server/inference.py model_server/schemas.py tools/benchmark_latency.py tests/test_model_server_inference_runtime.py tests/test_model_server_api_runtime.py tests/test_model_server_benchmark_latency.py
git commit -m "feat: report generation resolution in benchmarks"
```

---

### Task 4: Update the L4 Contract and Verify the Model Branch

**Files:**
- Modify: `.env.example`
- Modify: `model_server/README.md`
- Modify: `docs/L4_BENCHMARK_CHECKLIST.md`
- Modify: `docs/model_server_handoff.md`
- Modify: `.codex/project-ledger/PROJECT_STATE.md`
- Modify: `.codex/project-ledger/NEXT_STEPS.md`
- Modify: `.codex/project-ledger/KNOWN_ISSUES.md`
- Modify: `.codex/project-ledger/BUILD_EVIDENCE.md`

**Interfaces:**
- Produces: an operator-visible 1024-vs-768 benchmark matrix and rollback setting.

- [ ] **Step 1: Document the exact environment contract**

Add `FAST_BACKGROUND_SIZE=768`, state that `IMAGE_SIZE=1024` is the final output,
and include the five one-variable-at-a-time benchmark variants from the design.

- [ ] **Step 2: Run the complete local model branch gate**

```bash
python -m pytest -q
python -m ruff check app model_server tests tools
python -m compileall -q app model_server tests tools
python -m pip check
git diff --check
```

Expected: every command exits 0. Do not run a full clean model dependency install
locally because its downloads exceed 100 MB; record that exact L4 clean install
remains the external acceptance gate.

- [ ] **Step 3: Update the continuity ledger with fresh command evidence**

Record commands, timestamps, results, branch head, dirty state, and the remaining
L4 resolver/benchmark gate. Validate with:

```bash
python "$USERPROFILE/.codex/skills/project-continuity-ledger/scripts/ledger.py" check . --json
```

- [ ] **Step 4: Commit docs and evidence locally**

```bash
git add .env.example model_server/README.md docs/L4_BENCHMARK_CHECKLIST.md docs/model_server_handoff.md .codex/project-ledger
git commit -m "docs: hand off 768 background benchmark"
```

---

### Task 5: Prove Model Result to Shorts Integration and Build a Local Combined Branch

**Files:**
- Create in Shorts worktree: `tests/test_model_to_video_integration.py`
- Modify only if the failing test requires it: the exact backend contract file named by the failure.
- Use existing Shorts implementation under `app/backend/services/storyboard.py`, `video_renderer.py`, and `video_workflow.py`.

**Interfaces:**
- Consumes: `ToneResult.result_id` and `/files/outputs/...` URLs created by `ModelServerGenerationService`.
- Produces: a completed `VideoJob` whose storyboard image is the persisted model-backed ad file.

- [ ] **Step 1: Add a failing integration test in the Shorts worktree**

The test must use `ModelServerGenerationService` with injected fake HTTP responses,
write the returned background through the real overlay path, persist the resulting
`ToneResult` in history, build a storyboard from its `result_id`, and run
`VideoWorkflowService` with a fake renderer that records `storyboard.image_path`.
Assert the recorded path is the real generated output file and the video job ends
with `render_status=completed`.

- [ ] **Step 2: Run the integration test and verify RED**

Run in the Shorts worktree:

`python -m pytest tests/test_model_to_video_integration.py -q`

Expected: FAIL at the first missing or inconsistent model-to-storyboard contract.

- [ ] **Step 3: Apply only the minimal contract fix**

If the failure is the remote product URL contract, apply the PR #15 behavior:
resolve product URLs against `BACKEND_PUBLIC_URL`, restrict them to the backend
origin, and keep model output fetching through `MODEL_SERVER_URL`. Do not copy GPU
pipeline implementation into the Shorts modules.

- [ ] **Step 4: Run focused and full Shorts gates**

```bash
python -m pytest tests/test_model_to_video_integration.py tests/test_storyboard.py tests/test_video_workflow.py tests/test_video_renderer.py -q
python -m pytest -q
python -m ruff check app tests scripts
python -m compileall -q app scripts
python -m pip check
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 5: Create local Shorts implementation checkpoints without pushing**

Stage only reviewed Shorts source, docs, assets metadata, and tests; confirm media,
logs, OAuth data, and local stores remain ignored. Commit locally with:

```bash
git commit -m "feat: add reviewed rush-hour Shorts workflow"
```

- [ ] **Step 6: Create an unpushed local integration worktree**

Create `codex/model-shorts-integration` from the verified model branch and
cherry-pick the reviewed Shorts implementation commit. Resolve overlapping backend,
configuration, docs, and tests by preserving both contracts rather than choosing
one wholesale.

- [ ] **Step 7: Verify the combined local branch**

Run the full pytest, Ruff, compileall, pip check, diff check, credential scan, and
Git-ignore audit. Run local FastAPI/Streamlit browser E2E with YouTube disabled;
create a rush-hour result, render a Short, approve one, reject one, and verify only
the approved video is exposed in its time window.

- [ ] **Step 8: Stop before remote publication**

Report the model commits, Shorts commit, integration branch, verification evidence,
remaining L4 clean-install/benchmark gate, and exact files ready for review. Do not
push or update any PR.
