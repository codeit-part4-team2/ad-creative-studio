# Aspect-Ratio Presets Design

**Date:** 2026-08-18
**Branch:** `codex/aspect-ratio-presets`
**Base:** `origin/main @ 1ff7afd`
**Status:** User-approved direction; written design awaiting review before implementation

## Goal

Let a user choose one or two validated advertising aspect ratios before
generation, and generate each selected ratio natively instead of fitting one
square model result into every export canvas. This removes the white letterbox
seen in the current 4:5 and wide outputs while preserving product proportions.

The first release supports exactly four presets:

| API key | User label | Fast background | Internal composite | Export size | Intended use |
|---|---|---:|---:|---:|---|
| `thumbnail` | 정사각형 1:1 | 768x768 | 1024x1024 | 1080x1080 | 대표 이미지, 정사각형 피드 |
| `sns_card` | SNS 피드 4:5 | 672x840 | 896x1120 | 1080x1350 | Instagram and social feed |
| `story_vertical` | 쇼츠·스토리 9:16 | 576x1024 | 720x1280 | 1080x1920 | Shorts, Reels, Stories |
| `wide_banner` | 웹 배너 16:9 | 1024x576 | 1280x720 | 1280x720 | Web and video banners |

All background and composite dimensions are divisible by eight. Background
pixel area stays at or below the current 768x768 fast-generation baseline, and
composite pixel area stays at or below the current 1024x1024 square baseline.
L4 latency, peak VRAM, and visual quality still require an
operating-environment benchmark before a production merge.

## Non-goals

- No arbitrary width/height or free-form `x:y` input.
- No outpainting of a square result into a different ratio.
- No automatic focal-point or saliency crop.
- No parallel GPU inference for two selected ratios; the existing single-GPU
  serialization remains authoritative.
- No change to tone, time-slot, TTS, Shorts narration, or YouTube publishing.
- No migration or deletion of existing History files.

## Team delivery order and ownership

Delivery follows the team's agreed sequence and each stage hands a stable
artifact to the next owner:

1. **성치용 + Codex:** implement the preset contract, backend/model generation,
   native-ratio composition, compatibility behavior, tests, and handoff notes
   on the model PR branch. This stage does not implement the final web controls.
2. **김재헌A:** apply the branch to the serving environment and complete the L4
   dimensions, latency, VRAM, cache, and failure checks.
3. **박재철:** implement and verify the ratio selector, workload display,
   ratio-aware result preview, and end-to-end UI behavior against the stabilized
   API contract.
4. **유수빈:** review the generated creatives and UI presentation for crop,
   composition, text legibility, product preservation, and overall design
   quality across all four presets.
5. **팀장:** provide the final integrated feedback and merge/revision decision.

The handoff is sequential. A later owner may report an issue to an earlier stage,
but UI or design approval must not be presented as complete before its owner has
actually reviewed it.

## User experience

The following is the accepted UI contract for 박재철's follow-up phase. The
create page adds a required `광고 비율 선택` section in the final style step.
`정사각형 1:1` is selected by default.

```text
광고 비율 선택 (최대 2개)
☐ 정사각형 1:1
☐ SNS 피드 4:5
☐ 쇼츠·스토리 9:16
☐ 웹 배너 16:9
```

Rules:

1. At least one and at most two presets must be selected.
2. Once two are selected, the other unchecked options are disabled and a
   `최대 2개까지 선택할 수 있어요` hint remains visible.
3. The confirmation panel shows the real workload:
   `톤 4종 x 시간대 N개 x 비율 M개 = K개 이미지 생성`.
4. The request button remains disabled if the ratio count is outside 1..2.
5. The API remains the final enforcement boundary; direct requests with zero,
   three, duplicate, or unknown presets return a validation error.

## Public application contract

`GenerationRequest.output_formats` remains the request field to avoid a second
parallel concept in the API. Its accepted values become the four preset keys
above and its cardinality becomes 1..2. The default is `['thumbnail']`, so old
clients that omit the field still receive a valid square result.

The Next.js client explicitly sends the selected values in the UI follow-up:

```json
{
  "product_id": "prd_123",
  "time_slots": ["commute_pm"],
  "output_formats": ["sns_card", "story_vertical"]
}
```

`ToneResult.images` keeps the existing `format -> URL` mapping. A tone/time
result therefore remains one domain result and contains one or two image URLs.
The result count does not multiply, but generation job work and progress do:

```text
total_count = tones x time_slots x output_formats
estimated_seconds = tones x time_slots x output_formats x seconds_per_generation
```

The legacy `detail_banner` key is not offered or accepted for new requests.
Existing History records and download routes continue to display and download
it because those paths read keys already stored in `result.images` rather than
validating a new generation request.

## Shared preset definition

Python owns one canonical preset module containing:

- allowed request key;
- Korean label;
- aspect ratio;
- internal background dimensions;
- internal composed-image dimensions;
- export dimensions;
- filename-safe suffix.

The backend overlay and model server import this module rather than copying
width and height tables. In the UI follow-up, the web client adds a typed display
table with the same four keys. An API contract test verifies that all four values
are accepted while unknown values are rejected.

## Backend generation flow

`build_generation_plan()` continues to produce tone x time-slot items. For each
item, `GenerationService` performs the following:

1. Start copy generation once for the tone/time item.
2. Iterate selected presets in request order.
3. Request one native-ratio image from the model server for the current preset.
4. Fetch the generated image and confirm its ratio matches the selected preset.
5. Resize only between equal aspect ratios to the export size; never add white
   padding and never stretch across different ratios.
6. Draw the same approved headline/subcopy using preset-aware safe margins.
7. Store the formatted URL under the preset key in `ToneResult.images`.
8. Increment job progress after each completed preset.

Copy generation is awaited once and reused by both selected ratios. GPU model
requests stay sequential. A failure in either selected ratio fails the whole
job instead of returning a silently incomplete result.

The local mock path creates a placeholder directly at each preset's export
size, preserving the same output contract without model-server access.

## Model-server contract and pipeline

`InferRequest` adds an allow-listed `output_format` preset with `thumbnail` as
the backward-compatible default. New backend callers always send it explicitly,
and no caller can send arbitrary dimensions.

The model server resolves the preset and passes explicit width/height values
through `InferenceEngine` into `DiffusersGenerationPipeline`:

- fast background generation uses the preset's background dimensions;
- the generated background is resized only to the same-ratio internal composed
  dimensions;
- the cached segmented product is fitted to a transparent canvas with those
  composed dimensions;
- background and product canvases must match exactly before alpha composition.

The existing product download and segmentation cache remains keyed by product,
so selecting two ratios must not run `rembg` twice. Ratio-specific canvases are
derived cheaply from the cached segmented product after the cache lookup.

The quality-regenerate profile receives ratio-specific `product_on_white`,
alpha mask, and Canny artifacts derived from the same cached segmentation. Its
ControlNet/IP-Adapter behavior is preserved, but the production acceptance gate
continues to use the confirmed `fast_composite` profile.

`InferResponse` adds `output_format`, `background_width`,
`background_height`, `output_width`, and `output_height`. Existing scalar
`background_size` and `output_size` fields remain populated only for square
requests and become `null` for non-square requests, avoiding misleading metrics.

## Clean source and Shorts behavior

Only a rush-hour `story_vertical` generation persists the text-free clean image
as `source_image_url`. Other presets are kept in memory only long enough to
create their formatted export. This preserves the existing bounded-storage
decision while giving Shorts a native 9:16 hero image.

For a rush-hour result:

- if `story_vertical` is selected, the comic Shorts button is available;
- if it is not selected, the UI says
  `쇼츠를 만들려면 9:16 비율로 광고를 다시 생성해 주세요`;
- a legacy result with `story_vertical` data but no clean source retains the
  existing clean-source regeneration warning.

The video workflow continues to consume `source_image_url`; no new video schema
is required.

## Result and History UI

Each tone/time result card contains ratio tabs for the formats present in
`result.images`. The first selected request format is the initial tab.

The preview container uses the selected preset's real CSS `aspect-ratio` and
does not force `aspect-square` or use a crop that hides part of the export.
Download buttons use explicit labels:

- `정사각형 광고 (1:1)`
- `SNS 피드 광고 (4:5)`
- `쇼츠·스토리 광고 (9:16)`
- `웹 배너 광고 (16:9)`

Legacy keys, including `detail_banner`, retain display labels and remain
downloadable. Unknown stored keys fall back to their raw key without crashing.

## Error handling and safety

- Request validation rejects zero, more than two, duplicate, or unknown presets.
- Model-server validation rejects unknown preset values before GPU work.
- Generated dimensions must be positive, within the existing pixel/byte limits,
  and match the selected aspect ratio within a one-pixel rounding tolerance.
- The backend rejects a mismatched model result before copy overlay so square
  output cannot silently reintroduce padding.
- Job state reports the failing tone, time slot, and preset without exposing a
  traceback to the user.
- Existing one-worker and GPU-lock requirements remain unchanged.

## Performance expectations and external gate

Native generation changes model calls from `tones x time_slots` to
`tones x time_slots x selected ratios`. Selecting two ratios is expected to
approximately double the generation stage, though preprocessing should remain a
single cache miss per product and subsequent ratio work should be a cache hit.

Before production merge, the serving owner must run an L4 comparison for all
four presets using the confirmed fast profile and report:

- P50/P95 and failure count;
- peak VRAM;
- actual output width/height;
- product preservation and crop safety;
- absence of white bars, duplicated products, generated text, and dominant
  background props;
- two-preset sequential request total time and cache behavior.

No preset becomes production-ready solely from local mock or CPU tests.

## Test strategy

### Backend and contract

- exactly one and exactly two presets are accepted;
- zero, three, duplicate, and unknown presets are rejected;
- job total and estimated time include ratio count;
- copy generation runs once per tone/time item;
- model generation runs once per selected ratio;
- ratio failure fails the complete job;
- legacy History/download data remains readable.

### Model server

- every preset resolves to the intended background and output dimensions;
- pipeline receives width and height, not a square scalar;
- cached segmentation is reused across two ratios;
- product and background canvas dimensions match;
- response dimension metadata is exact;
- unknown presets fail before pipeline invocation.

### Overlay and files

- all four saved outputs have exact export dimensions;
- no white border exists on constant-color test backgrounds;
- product pixels are not stretched;
- filename and download keys are safe on Windows and Linux.

### Downstream UI acceptance (박재철)

- one preset is selected by default;
- a third choice is disabled after two selections;
- the generation payload contains the selected keys in order;
- workload copy includes ratio count;
- result tabs switch image and CSS aspect ratio correctly;
- legacy `detail_banner` still renders and downloads;
- Shorts guidance distinguishes missing 9:16 from a missing legacy clean source.

### Final local gate

- focused Python tests;
- full `python -m pytest -q`;
- changed-file Ruff and compileall;
- web lint, type check, and production build are required in the downstream UI
  phase; they are also required in this phase if any shared web file changes;
- project ledger check and `git diff --check`;
- no commit, push, PR, deployment, or VM change without explicit authorization.

## PR draft text

### Title

`Add native aspect-ratio generation presets`

### Summary

- add 1:1, 4:5, 9:16, and 16:9 generation presets with a maximum of two per request;
- generate and composite each selected ratio natively instead of letterboxing a square source;
- validate the one-to-two preset API contract and account for ratio work in job progress;
- preserve legacy History downloads and require native 9:16 clean source for new rush-hour Shorts.

### Validation requirements

The model PR body must include fresh local Python test results and explicitly
state that UI implementation is a downstream owner task. L4 measurements remain
pending until 김재헌A runs the external acceptance checks above. The PR remains
Draft through server application, UI integration, 유수빈's design review, and the
team lead's final feedback unless the team lead explicitly changes that policy.
