# Decisions

| Date | Status | Decision | Rationale | Evidence |
|---|---|---|---|---|
| 2026-08-10 | `[VERIFIED]` | Generate only the `fast_composite` background at 768x768; retain 1024x1024 final output and product canvas. | Reduce SDXL latent work without lowering customer-visible output or source product fidelity. | User approval and `docs/superpowers/specs/2026-08-10-model-speed-shorts-integration-design.md` |
| 2026-08-10 | `[VERIFIED]` | Keep model-serving and Shorts changes in separate review units. | Preserve PR #15 benchmark scope and keep FFmpeg/approval/YouTube review independent. | Current branches and approved design |
