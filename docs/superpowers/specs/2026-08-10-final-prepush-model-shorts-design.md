# Final Pre-Push Model and Shorts Design

## 1. Goal

Prepare the existing model-server, rush-hour Shorts generator, and their local
integration for review immediately before Git push. Remote branches, Draft PR
#15, YouTube, and deployment remain unchanged.

## 2. Confirmed baseline

- `codex/model-server-optimization` contains the 768x768 fast-background path,
  1024x1024 final output, dependency repair, and benchmark metadata.
- `codex/rush-hour-shorts-design` contains persisted Shorts jobs, reviewed
  render/approval/rejection, rush-hour exposure, and disabled-by-default
  YouTube publishing.
- `codex/model-shorts-integration` combines both review units for local
  regression testing only.
- The serving owner reported L4 fast-profile results for 4, 6, and 8 steps.
  The report is useful evidence but does not prove the requested 768 setting
  until `background_size=768` and `output_size=1024` are captured.

## 3. Fast VAE design

Both inference profiles load `madebyollin/sdxl-vae-fp16-fix` explicitly and
pass that instance into the SDXL pipeline constructor. The quality profile
already follows this pattern. Applying the same component to `fast_composite`
prevents the stock SDXL VAE from forcing FP32 decode and avoids the associated
`AutoencoderKL` and deprecated `upcast_vae` warnings.

The base model, LCM-LoRA, ControlNet, IP-Adapter, output size, background size,
and default step count remain unchanged. The VAE model card notes that decoded
output can differ slightly from the stock VAE, so the change remains subject to
an L4 same-seed visual comparison before merge.

## 4. GPU queue timing design

Preprocessing remains concurrent and GPU generation remains protected by one
process-local lock. The engine measures elapsed time while acquiring that lock
as `gpu_queue_wait_sec` and also publishes the same value in
`stage_times_sec["gpu_queue_wait"]`.

`generate` continues to measure only the actual pipeline call. `gen_time_sec`
continues to cover the complete request and therefore includes queueing. This
separation makes a queued six-second response distinguishable from a
three-second generation without changing scheduling behavior.

The server must continue to run with exactly one Uvicorn worker per L4. A
process-local lock cannot coordinate independent worker processes.

## 5. API and benchmark contract

Successful `/infer` responses add the optional numeric field
`gpu_queue_wait_sec`. Existing clients remain compatible. The benchmark tool
already summarizes every stage, so the new `gpu_queue_wait` stage automatically
appears in stage medians without a new command-line option.

The final external benchmark request is:

1. Confirm `background_size=768` and `output_size=1024` for B/C/D.
2. Compare B0 (1024 background, 4 steps) with B (768 background, 4 steps).
3. Compare current B with B plus the FP16-safe VAE using the same seed.
4. Record p50, p95, stage medians, queue wait, peak VRAM, warnings, failures,
   and same-seed image samples.

## 6. Shorts and integration boundary

No new Shorts behavior is introduced. The existing Shorts worktree is rerun
through its full test and static gates. The reviewed model commit is then
cherry-picked into the local integration branch and the combined suite is run
again. YouTube remains disabled and no OAuth or upload request is made.

## 7. Acceptance

- A focused test proves fast and quality profiles both receive the explicit
  FP16-safe VAE.
- A concurrency test proves the second request reports nonzero GPU queue wait
  while generation remains serialized.
- API serialization and benchmark summaries include the new timing contract.
- Model, Shorts, and combined integration suites pass with Ruff, compileall,
  `pip check`, and `git diff --check`.
- Credential and generated-artifact checks remain clean.
- All branches and worktrees are clean local commits, with no push, PR update,
  merge, deployment, or YouTube publication.
