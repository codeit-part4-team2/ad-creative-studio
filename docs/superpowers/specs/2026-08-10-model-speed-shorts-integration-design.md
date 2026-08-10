# Model Serving Speed, Dependency Safety, and Shorts Integration Design

- Date: 2026-08-10
- Repository: `codeit-part4-team2/ad-creative-studio`
- Model baseline: Draft PR #15, commit `f265d43`
- Related Shorts design: `docs/superpowers/specs/2026-08-08-rush-hour-shorts-youtube-design.md`

## 1. Context

The NVIDIA L4 benchmark for `quality_regenerate` completed successfully at commit
`f265d43`: ten warm requests completed without failure, generation P50 was 17.39
seconds, peak VRAM was 16.25 GB, and product preprocessing cache hits were 10/10.
The run also exposed a reproducible installation defect: the exact pin
`numpy==2.2.6` does not satisfy `rembg[gpu]==2.0.76`, which requires NumPy 2.3 or
newer. Python 3.10 is outside the model-server runtime contract; Python 3.11 is
the minimum supported version.

The approved product direction is to keep the high-quality 30-step path as a
comparison profile, accelerate only the default background-generation path, and
feed completed ad images into the already designed rush-hour Shorts workflow.

## 2. Goals

1. Make a clean Python 3.11 installation reject incompatible exact dependency
   pins before an L4 deployment.
2. Reduce `fast_composite` latency without reducing the final image size or
   resampling the source product layer.
3. Preserve `quality_regenerate` at 1024x1024 and 30 steps as the comparison
   profile.
4. Connect persisted model-server ad results to deterministic 10-second Shorts
   through the existing `result_id` contract.
5. Keep model-serving changes reviewable separately from the Shorts feature.

## 3. Non-goals

- Do not change the SDXL base model, LCM-LoRA, ControlNet, IP-Adapter, or rembg
  model in this iteration.
- Do not add TensorRT, ONNX export, quantization, xFormers, or a new GPU service.
- Do not lower the final ad image below 1024x1024.
- Do not resize or regenerate the foreground product pixels after the existing
  alpha preparation step.
- Do not add TTS, narration, AI-generated music, or automatic unreviewed
  publishing.
- Do not merge, push, or update a remote PR until local tests and the next L4
  benchmark are ready for review.

## 4. Considered approaches

### 4.1 Approved: lower only the fast background resolution

Generate the `fast_composite` background at 768x768, resize that background to
1024x1024, and then alpha-composite the existing 1024x1024 product canvas. This
reduces SDXL latent work while keeping the customer-visible output and product
layer at the existing size. The original 1024 background setting remains
available through configuration for rollback and A/B comparison.

### 4.2 Rejected for now: keep 1024 and rely only on compilation

`torch.compile` can improve steady-state latency after expensive warm-up, but it
does not reduce the amount of diffusion work and may make cold-start behavior
harder to demo. It remains an explicit benchmark variant rather than the sole
optimization.

### 4.3 Rejected for now: replace or export the model

SDXL Turbo, Lightning, TensorRT, ONNX, or quantization could reduce latency more,
but each changes quality, dependency, deployment, or licensing risk. Those
changes require a separate model-quality decision and are outside this bounded
fix.

## 5. Architecture and branch boundaries

The work stays in two review units:

1. The PR #15 branch receives dependency compatibility checks, configurable
   background resolution, output-size normalization, telemetry, and benchmark
   documentation.
2. The Shorts branch consumes persisted generation results through `result_id`
   and remains a separate follow-up PR. It does not duplicate or import the GPU
   pipeline.

Until PR #15 is merged, the Shorts branch may be tested locally on top of the
PR #15 commit, but its remote PR must target a base that contains the model
contract. This avoids placing model, FFmpeg, approval, and YouTube changes in a
single review.

## 6. Dependency safety design

`model_server/requirements.txt` will pin NumPy to `2.3.5`, satisfying both
`rembg[gpu]==2.0.76` (`numpy>=2.3,<3`) and
`opencv-python-headless==5.0.0.93` (`numpy>=2` on Python 3.11). The existing
project requirement `requires-python = ">=3.11"` remains authoritative.

The existing exact-pin test only checks syntax and did not detect incompatible
constraints. A metadata-level compatibility test will assert that the selected
NumPy version satisfies the model-server direct constraints. CI will also run a
clean dependency resolution command for `model_server/requirements.txt`
without loading model weights. The test must fail if a future pin falls outside
the declared rembg or OpenCV range.

No claim of a reproducible environment is allowed until the clean resolver and
`pip check` both pass on Python 3.11.

## 7. Fast background design

`InferenceConfig` gains `fast_background_size`, loaded from
`FAST_BACKGROUND_SIZE`, with a default of 768. Validation requires the value to
be positive, divisible by 8, and no larger than `IMAGE_SIZE`.

For `fast_composite` only:

1. SDXL receives `width=fast_background_size` and
   `height=fast_background_size`.
2. The generated RGB background is resized to `IMAGE_SIZE x IMAGE_SIZE` with
   Lanczos when the sizes differ.
3. The inference engine composites the unchanged prepared product canvas over
   the normalized background.
4. The saved output remains 1024x1024 and `product_preserved=true` continues to
   mean source alpha composition, not a learned similarity score.

For `quality_regenerate`, width and height remain `IMAGE_SIZE` and no new resize
is introduced.

The response metadata gains `background_size` and `output_size` so benchmark
records cannot confuse a 768 background run with a 1024 run. The benchmark tool
records those fields alongside P50/P95, stage timings, VRAM, profile, and steps.

## 8. Optional runtime acceleration

TF32 and `torch.compile` remain opt-in benchmark variants. They must not be
silently enabled together with the resolution change because that would make
the source of any latency or quality difference ambiguous.

The L4 matrix is run one variable at a time:

1. 1024 background, 4 steps, compile off.
2. 768 background, 4 steps, compile off.
3. 768 background, 6 steps, compile off.
4. 768 background, 8 steps, compile off.
5. Selected 768 step count, compile on after compile warm-up.

The selected default must have zero OOM failures and visually acceptable
background quality. Exact latency is not predicted locally; it is established
only by the L4 rerun.

## 9. Shorts integration data flow

The integration uses stored service data rather than a direct GPU-to-FFmpeg
call:

```text
Model server /infer
  -> backend saves generated ad image URLs
  -> generation result receives result_id
  -> History requests a Shorts job for that result_id
  -> StoryboardBuilder resolves the stored ad images and factual copy
  -> FFmpeg renders a 1080x1920, 30 fps, 10-second MP4
  -> operator approves or rejects
  -> approved video becomes eligible for its rush-hour window
  -> optional YouTube scheduling remains a separate reviewed action
```

The Shorts job stores a source fingerprint that includes the selected generated
image URL and copy. Approval fails if the source image, copy, or rendered MP4
changed after preview. Model generation failure creates no Shorts job. Shorts
rendering or YouTube failure does not invalidate an already saved ad image.

## 10. Error handling

- Invalid or incompatible dependency pins fail CI before deployment.
- Invalid `FAST_BACKGROUND_SIZE` fails configuration startup with the variable
  name in the error.
- A generated background with an unexpected size is normalized before
  compositing; a missing image remains an inference failure.
- A missing `result_id`, non-rush-hour result, missing generated image, or source
  fingerprint mismatch returns an explicit 4xx workflow response.
- YouTube remains disabled unless OAuth is configured and the operator selects
  publishing during approval.

## 11. Verification and acceptance

### Model-serving acceptance

- The exact-pin test and the semantic NumPy compatibility test pass.
- A clean Python 3.11 resolver accepts the full model-server requirements and
  `pip check` reports no broken requirements.
- Unit tests prove 768 is used only by `fast_composite` and 1024 remains in the
  quality profile.
- Unit tests prove 768 output is normalized to 1024 before product composition.
- API and benchmark metadata report both background and output sizes.
- Existing model-server tests and repository CI remain green.

### L4 acceptance

- Warm runs are measured at least ten times per matrix entry.
- P50/P95, cold start, stage timings, peak VRAM, cache hits, and failures are
  recorded.
- At least 20 varied products are visually reviewed for masks, logos, buttons,
  and product/background placement.
- Distinct-product concurrent preprocessing is checked separately from the
  intentionally serialized GPU generation stage.

### Shorts acceptance

- A real persisted model-server result creates a playable 10-second MP4.
- The video is 1080x1920, 30 fps, H.264/AAC, and uses only stored factual copy.
- Approval and rejection survive backend restart.
- Only an approved video appears in the matching rush-hour exposure response.
- Tests and local browser E2E perform no external YouTube upload.

## 12. Delivery gate

Local implementation may proceed after this design is reviewed. Remote changes
remain separated: update Draft PR #15 only after the dependency and model tests
pass; prepare the Shorts follow-up only after its integration tests pass. PM
approval and the new L4 benchmark remain required before merge.
