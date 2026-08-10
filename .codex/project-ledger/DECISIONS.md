# Decisions

| Date | Status | Decision | Rationale | Evidence |
|---|---|---|---|---|
| 2026-08-10 | `[VERIFIED]` | Generate only the `fast_composite` background at 768x768; retain 1024x1024 final output and product canvas. | Reduce SDXL latent work without lowering customer-visible output or source product fidelity. | User approval and `docs/superpowers/specs/2026-08-10-model-speed-shorts-integration-design.md` |
| 2026-08-10 | `[VERIFIED]` | Keep model-serving and Shorts changes in separate review units. | Preserve PR #15 benchmark scope and keep FFmpeg/approval/YouTube review independent. | Current branches and approved design |
| 2026-08-10 | `[VERIFIED]` | Keep `fast_composite` at 4 steps by default. | The serving owner reported the lowest p50/p95 for 4 steps with the same 10/10 preservation response as 6 and 8 steps; final visual selection remains external. | User-approved final pre-push design and external report recorded in `model_server/README.md` |
| 2026-08-10 | `[VERIFIED]` | Inject `madebyollin/sdxl-vae-fp16-fix` into both model profiles. | Avoid stock SDXL VAE FP32 decode/upcast warnings while retaining the already-used quality-profile VAE. | `f22a65b`, focused RED/GREEN test, model card states MIT and `force_upcast=false` |
| 2026-08-10 | `[VERIFIED]` | Report GPU lock wait separately from generation. | Concurrent requests are intentionally serialized; operators need queue time separated from actual pipeline time. | `a286cf2`, focused concurrency/API tests |
