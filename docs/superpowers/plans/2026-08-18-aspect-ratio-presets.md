# Native Aspect-Ratio Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend and model-server support for one or two native 1:1, 4:5, 9:16, or 16:9 advertisement outputs without white letterboxing or product stretching.

**Architecture:** A single Python preset registry owns request keys and all background, composite, and export dimensions. The backend calls `/infer` once per selected preset and overlays copy only onto a same-ratio source; the model server derives ratio-specific product artifacts from one cached segmentation and runs GPU generations sequentially. UI implementation remains a downstream handoff to 박재철 after 김재헌A validates the server branch on L4.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, Pillow, Diffusers/SDXL, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-18-aspect-ratio-presets-design.md`

## Global Constraints

- Accepted new-generation keys are exactly `thumbnail`, `sns_card`, `story_vertical`, and `wide_banner`.
- Every generation request contains one or two unique output formats; omitted input defaults to `thumbnail`.
- `detail_banner` remains readable in stored History/download data but is rejected for new generation requests.
- Fast background sizes are 768x768, 672x840, 576x1024, and 1024x576 in preset order.
- Internal composite sizes are 1024x1024, 896x1120, 720x1280, and 1280x720.
- Export sizes are 1080x1080, 1080x1350, 1080x1920, and 1280x720.
- Never pad with white, stretch across aspect ratios, accept arbitrary dimensions, or issue two GPU generations concurrently.
- Preserve the current `/infer` default as `thumbnail` for callers that omit `output_format`, including Shorts scene-image calls.
- Persist a clean source only for rush-hour `story_vertical`; do not reuse 1:1, 4:5, or 16:9 as a Shorts source.
- Do not modify final web controls in this branch; UI ownership follows the team handoff sequence.
- Do not stage, commit, push, open a PR, deploy, or change the VM in this implementation run.

---

### Task 1: Canonical preset registry and request workload contract

**Files:**
- Create: `app/image_presets.py`
- Modify: `app/prompt/schemas.py`
- Modify: `app/prompt/templates.py`
- Modify: `app/backend/schemas/generation.py`
- Modify: `app/backend/api/generations.py`
- Test: `tests/test_aspect_ratio_presets.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `OutputFormatLiteral`, immutable `ImagePreset`, `IMAGE_PRESETS`, `get_image_preset(key)`, and `estimate_seconds(num_tones, num_time_slots, num_output_formats=1)`.
- Consumes: existing Pydantic request parsing and job dictionaries.

- [ ] **Step 1: Write failing registry and schema tests**

Create tests that assert the exact preset tuples and request rules:

```python
@pytest.mark.parametrize(
    ("key", "background", "composite", "export"),
    [
        ("thumbnail", (768, 768), (1024, 1024), (1080, 1080)),
        ("sns_card", (672, 840), (896, 1120), (1080, 1350)),
        ("story_vertical", (576, 1024), (720, 1280), (1080, 1920)),
        ("wide_banner", (1024, 576), (1280, 720), (1280, 720)),
    ],
)
def test_image_presets_have_exact_dimensions(key, background, composite, export):
    preset = get_image_preset(key)
    assert preset.background_size == background
    assert preset.composite_size == composite
    assert preset.export_size == export

def test_generation_request_defaults_to_square():
    request = GenerationRequest(product_id="p", time_slots=["morning"])
    assert request.output_formats == ["thumbnail"]

@pytest.mark.parametrize("formats", [[], ["thumbnail", "thumbnail"], ["thumbnail", "sns_card", "story_vertical"], ["detail_banner"]])
def test_generation_request_rejects_invalid_format_sets(formats):
    with pytest.raises(ValidationError):
        GenerationRequest(product_id="p", time_slots=["morning"], output_formats=formats)
```

- [ ] **Step 2: Run the tests and verify the expected failures**

Run: `python -m pytest tests/test_aspect_ratio_presets.py -q`

Expected: collection/import failure because `app.image_presets` does not exist, followed by validation failures until the registry and request constraints are implemented.

- [ ] **Step 3: Implement the immutable registry and validated request field**

Create a frozen, slotted dataclass and exact allow-list:

```python
OutputFormatLiteral = Literal["thumbnail", "sns_card", "story_vertical", "wide_banner"]

@dataclass(frozen=True, slots=True)
class ImagePreset:
    key: OutputFormatLiteral
    label: str
    background_size: tuple[int, int]
    composite_size: tuple[int, int]
    export_size: tuple[int, int]

IMAGE_PRESETS: Final[Mapping[OutputFormatLiteral, ImagePreset]] = MappingProxyType({...})

def get_image_preset(key: str) -> ImagePreset:
    try:
        return IMAGE_PRESETS[cast(OutputFormatLiteral, key)]
    except KeyError as exc:
        raise ValueError(f"unsupported output format: {key}") from exc
```

Import `OutputFormatLiteral` into `app.prompt.schemas`. Define the request field as:

```python
output_formats: list[OutputFormatLiteral] = Field(
    default_factory=lambda: ["thumbnail"], min_length=1, max_length=2
)

@field_validator("output_formats")
@classmethod
def output_formats_must_be_unique(cls, values):
    if len(values) != len(set(values)):
        raise ValueError("output_formats must not contain duplicates")
    return values
```

Remove the obsolete new-generation `OUTPUT_FORMATS` table from templates and update `estimate_seconds` to multiply by `num_output_formats`.

- [ ] **Step 4: Add failing workload tests and verify RED**

Change the API test to request two formats and assert `4 tones x 2 slots x 2 formats = 16`. Assert `estimated_seconds == estimate_seconds(4, 2, 2)` and keep `build_generation_plan()` at eight prompt items.

Run: `python -m pytest tests/test_api.py::test_generate_returns_202_and_expected_total_count tests/test_api.py::test_output_formats_do_not_increase_model_generation_count -q`

Expected: FAIL because totals and estimates still ignore output format count.

- [ ] **Step 5: Make workload accounting pass**

In `create_generation`, compute:

```python
format_count = len(req.output_formats)
total = len(req.tones) * len(req.time_slots) * format_count
est = estimate_seconds(len(req.tones), len(req.time_slots), format_count)
```

Update comments so the prompt plan remains `tones x time_slots`, while job work is `tones x time_slots x formats`.

- [ ] **Step 6: Verify Task 1 green and leave an uncommitted checkpoint**

Run: `python -m pytest tests/test_aspect_ratio_presets.py tests/test_api.py -q`

Run: `git diff --check`

Expected: all selected tests pass; working tree changes remain unstaged and uncommitted.

---

### Task 2: `/infer` preset contract and dimension metadata

**Files:**
- Modify: `app/backend/services/model_server_client.py`
- Modify: `model_server/schemas.py`
- Modify: `model_server/main.py`
- Modify: `model_server/inference.py`
- Modify: `model_server/pipelines.py`
- Test: `tests/test_model_server_api_runtime.py`
- Test: `tests/test_model_server_generation.py`
- Test: `tests/test_model_server_inference_runtime.py`

**Interfaces:**
- Consumes: `OutputFormatLiteral` and `get_image_preset()` from Task 1.
- Produces: `/infer` request field `output_format="thumbnail"`, explicit response fields `background_width`, `background_height`, `output_width`, `output_height`, and `InferenceEngine.run(..., output_format: str)`.

- [ ] **Step 1: Write failing client and API contract tests**

Add a payload capture test:

```python
payload = _generation_payload("p", "/files/p.png", "modern", "prompt", None, "morning", "sns_card")
assert payload["output_format"] == "sns_card"
```

Post `/infer` without `output_format` and assert the fake engine receives `thumbnail`; post with `story_vertical` and assert it receives `story_vertical`; post `detail_banner` and assert HTTP 422. Extend success metadata assertions to exact width and height values.

- [ ] **Step 2: Run contract tests and verify RED**

Run: `python -m pytest tests/test_model_server_api_runtime.py tests/test_model_server_generation.py -q`

Expected: FAIL because the request field, client argument, engine forwarding, and explicit metadata do not exist.

- [ ] **Step 3: Implement request forwarding and backward-compatible response fields**

Add `output_format: OutputFormatLiteral = "thumbnail"` to `InferRequest`, pass it from `main.infer()` into `engine.run()`, and add the same required argument to backend async/sync request helpers. Add these optional fields to `GenerationResult`, `InferenceResult`, and `InferResponse`:

```python
output_format: OutputFormatLiteral | None = None
background_width: int | None = None
background_height: int | None = None
output_width: int | None = None
output_height: int | None = None
```

Keep `background_size` and `output_size`; populate them only when the corresponding width equals height.

- [ ] **Step 4: Write failing engine metadata test and verify RED**

Call `engine.run(..., output_format="sns_card")`, have the fake pipeline return 672x840 and 896x1120 metadata, and assert the result reports those dimensions while both scalar size fields are `None`.

Run: `python -m pytest tests/test_model_server_inference_runtime.py -q`

Expected: FAIL because `run()` and the pipeline protocol do not accept a preset and non-square metadata is not represented.

- [ ] **Step 5: Resolve and forward presets in the engine**

Resolve the preset before preprocessing and pass `background_size=preset.background_size` and `output_size=preset.composite_size` into the pipeline. Return the preset key and dimensions from the pipeline result. Do not accept raw dimensions from HTTP input.

- [ ] **Step 6: Verify Task 2 green and leave an uncommitted checkpoint**

Run: `python -m pytest tests/test_model_server_api_runtime.py tests/test_model_server_generation.py tests/test_model_server_inference_runtime.py -q`

Run: `git diff --check`

Expected: selected tests pass with the default square contract preserved.

---

### Task 3: Ratio-specific cached artifacts and SDXL pipeline dimensions

**Files:**
- Modify: `model_server/preprocessing.py`
- Modify: `model_server/inference.py`
- Modify: `model_server/pipelines.py`
- Test: `tests/test_model_server_preprocessing.py`
- Test: `tests/test_model_server_pipelines.py`
- Test: `tests/test_model_server_inference_runtime.py`

**Interfaces:**
- Consumes: preset background/composite tuples forwarded by Task 2.
- Produces: `ProductArtifacts.segmented_product`, `derive_product_artifacts(...)`, and `Pipeline.generate(..., background_size, output_size)`.

- [ ] **Step 1: Write failing artifact reuse tests**

Prepare the same cache key twice, derive 1:1 and 9:16 artifacts, and assert downloader and segmenter were each called once while derived `product_rgba`, `product_on_white`, alpha mask, and Canny images match the requested canvas.

```python
assert calls == {"download": 1, "segment": 1}
assert square.product_rgba.size == (1024, 1024)
assert vertical.product_rgba.size == (720, 1280)
assert vertical.product_on_white.size == (720, 1280)
```

- [ ] **Step 2: Run preprocessing tests and verify RED**

Run: `python -m pytest tests/test_model_server_preprocessing.py -q`

Expected: FAIL because raw segmentation is not retained and ratio derivation is absent.

- [ ] **Step 3: Retain segmentation and derive canvas-specific artifacts**

Add `segmented_product: Image.Image | None = None` to the end of `ProductArtifacts` to preserve existing test constructors. Production preprocessing stores the raw RGBA segmentation. Implement:

```python
def derive_product_artifacts(artifacts, *, canvas_size, fill_ratio, include_canny):
    source = artifacts.segmented_product or artifacts.product_rgba
    product_rgba = fit_product_rgba(source, canvas_size=canvas_size, fill_ratio=fill_ratio)
    alpha_mask = product_rgba.getchannel("A")
    product_on_white = Image.new("RGB", canvas_size, "white")
    product_on_white.paste(product_rgba, mask=alpha_mask)
    canny = make_canny_rgb(product_on_white) if include_canny else None
    return ProductArtifacts(product_rgba, product_on_white, alpha_mask, canny, source)
```

Call this helper in `InferenceEngine.run()` after the cache-backed `prepare()` and before pipeline generation.

- [ ] **Step 4: Write failing fast and quality pipeline dimension tests**

For `sns_card`, assert fast Diffusers receives `width=672`, `height=840`, returns a resized 896x1120 composite background, and metadata matches. For `story_vertical` quality mode, assert width 720 and height 1280 are passed to the ControlNet pipeline.

- [ ] **Step 5: Run pipeline tests and verify RED**

Run: `python -m pytest tests/test_model_server_pipelines.py -q`

Expected: FAIL because the pipeline still reads square scalar sizes from config.

- [ ] **Step 6: Implement explicit tuple dimensions**

Extend the pipeline protocol and `DiffusersGenerationPipeline.generate()` with:

```python
background_size: tuple[int, int]
output_size: tuple[int, int]
```

Use `width=background_size[0]`, `height=background_size[1]` for fast mode and `width=output_size[0]`, `height=output_size[1]` for quality mode. Resize only from the same-ratio background tuple to the composite tuple. Raise `ValueError` if the two tuples have different cross-multiplied ratios.

- [ ] **Step 7: Verify Task 3 green and leave an uncommitted checkpoint**

Run: `python -m pytest tests/test_model_server_preprocessing.py tests/test_model_server_pipelines.py tests/test_model_server_inference_runtime.py -q`

Run: `git diff --check`

Expected: selected tests pass; one cached segmentation serves both ratios.

---

### Task 4: Backend per-preset generation, native overlay, and clean-source rule

**Files:**
- Modify: `app/backend/services/generation_service.py`
- Modify: `app/backend/services/overlay.py`
- Test: `tests/test_generation_service.py`
- Test: `tests/test_model_server_generation.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: request formats and model-client `output_format` argument from Tasks 1-2.
- Produces: one sequential model call and one exact-ratio output per selected preset; progress incremented per preset; `source_image_url` only for rush-hour 9:16.

- [ ] **Step 1: Write failing native overlay tests**

Assert all four matching-ratio inputs export to exact dimensions without white edge pixels. Assert a square input passed as `sns_card` raises `ValueError` containing `aspect ratio` instead of padding.

```python
@pytest.mark.parametrize("key", IMAGE_PRESETS)
def test_overlay_exports_native_ratio_without_letterbox(key):
    preset = get_image_preset(key)
    source = Image.new("RGB", preset.composite_size, (12, 34, 56))
    result = overlay_copy(source, "", "", key)
    assert result.size == preset.export_size
    assert result.getpixel((0, 0)) == (12, 34, 56)
```

- [ ] **Step 2: Run overlay tests and verify RED**

Run: `python -m pytest tests/test_overlay.py -q`

Expected: FAIL because old format sizes and white-padding behavior remain.

- [ ] **Step 3: Replace padding with strict same-ratio resizing**

Make overlay resolve the canonical preset, compare ratios with integer cross multiplication, and use LANCZOS resize only when source and export share a ratio. Make `generate_and_save()` create a placeholder at `preset.composite_size` when no background is provided. Keep download filenames keyed by the validated preset.

- [ ] **Step 4: Write failing service sequencing and source tests**

Use a captured fake model client for one tone/time item with `output_formats=["sns_card", "story_vertical"]`. Assert calls are ordered `sns_card`, then `story_vertical`; each response image has its preset composite size; `completed_count == 2`; and only the 9:16 source is persisted. Add a rush-hour request without `story_vertical` and assert `source_image_url is None`.

- [ ] **Step 5: Run service tests and verify RED**

Run: `python -m pytest tests/test_generation_service.py tests/test_model_server_generation.py -q`

Expected: FAIL because the service makes one model call per prompt item, derives multiple padded exports, and progress counts prompt items only.

- [ ] **Step 6: Implement one sequential call per preset**

For each prompt-plan item, start copy generation once, then iterate `req.output_formats` in request order. For each preset:

1. set `current_step` to include time slot, tone, and preset;
2. call the model server with `output_format=preset_key`;
3. fetch the image and require the preset composite ratio;
4. save a clean source only when the time slot is rush hour and the key is `story_vertical`;
5. render and save exactly that one format;
6. increment `completed_count` and derive progress from `job["total_count"]`.

Await the copy task once before the first overlay and reuse the same headline/subcopy for both presets. Keep model calls inside the existing sequential loop.

- [ ] **Step 7: Verify Task 4 green and leave an uncommitted checkpoint**

Run: `python -m pytest tests/test_overlay.py tests/test_generation_service.py tests/test_model_server_generation.py -q`

Run: `git diff --check`

Expected: selected tests pass with no padding and correct progress/source behavior.

---

### Task 5: Handoff documentation and full local verification

**Files:**
- Modify: `docs/api_contract.md`
- Modify: `model_server/README.md`
- Modify: `docs/L4_BENCHMARK_CHECKLIST.md`
- Modify: `docs/prompt_spec.md`
- Modify: `docs/superpowers/specs/2026-08-18-aspect-ratio-presets-design.md` only if implementation reveals a factual correction
- Verify: all changed Python and test files

**Interfaces:**
- Consumes: final behavior from Tasks 1-4.
- Produces: server handoff instructions for 김재헌A and an API/UI contract for 박재철; no deployment or UI implementation.

- [ ] **Step 1: Update exact request/response documentation**

Document `output_format`, the four presets and exact dimensions, default square behavior, sequential two-preset generation, explicit width/height metadata, legacy scalar metadata, and the one-to-two backend request rule. Mark L4 figures as externally unverified rather than inserting estimates.

- [ ] **Step 2: Add the L4 owner checklist**

Require 김재헌A to measure all four formats for P50/P95, failure count, peak VRAM, actual dimensions, cache hit, product crop, white bars, duplicate products, generated text, dominant props, and total time for a two-format request.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest tests/test_aspect_ratio_presets.py tests/test_api.py tests/test_overlay.py tests/test_generation_service.py tests/test_model_server_generation.py tests/test_model_server_api_runtime.py tests/test_model_server_preprocessing.py tests/test_model_server_pipelines.py tests/test_model_server_inference_runtime.py -q
```

Expected: every selected test passes.

- [ ] **Step 4: Run the complete Python verification gate**

Run:

```powershell
python -m pytest -q
python -m ruff check app model_server tests
python -m compileall -q app model_server
git diff --check
```

Expected: pytest, Ruff, compileall, and diff check all exit 0. Record exact counts and any environment-only skips for the PR draft.

- [ ] **Step 5: Audit scope and prepare the unsubmitted PR text**

Run:

```powershell
git status --short --branch
git diff --stat
git diff --name-only
```

Verify no `web/` file, generated image, runtime store, credential, model weight, staged file, commit, push, PR, deployment, or VM change is present. Prepare the PR title `Add native aspect-ratio generation presets` and a body containing the exact local test evidence plus the remaining L4, UI, design, and team-lead handoffs.
