# Next Steps

| Priority | Status | Action | Acceptance evidence | Blocker |
|---|---|---|---|---|
| 1 | `[VERIFIED]` | Review the 2026-08-10 design and plan. | User approval and committed design/plan. | None |
| 2 | `[VERIFIED]` | Fix dependency pins and add semantic compatibility regression coverage. | Focused test and full local gate pass. | Clean L4 environment resolution remains external. |
| 3 | `[VERIFIED]` | Add configurable 768 fast background, 1024 normalization, and explicit size metadata. | 175 tests plus Ruff, compileall, pip check, and diff check pass. | L4 timing and visual quality remain external. |
| 4 | `[VERIFIED]` | Reconcile the locally verified Shorts worktree with the model result contract. | Combined branch passes 244 tests plus Ruff, compileall, pip check, diff, credential, and ignored-artifact gates at `929c3be`. | None |
| 5 | `[VERIFIED]` | Add FP16-safe VAE and separate GPU queue timing. | Model branch passes 178 tests plus Ruff, compileall, pip check, and diff check. | L4 same-seed VAE comparison remains external. |
| 6 | `[UNVERIFIED]` | Push or update the remote PR only after explicit user authorization. | Remote branch contains the reviewed local commits and CI result is recorded. | Push intentionally withheld. |
| 7 | `[UNVERIFIED]` | Obtain the original B/C/D JSON and confirm `background_size=768`, `output_size=1024`. | Response metadata and exact execution commit are recorded. | Serving VM access. |
| 8 | `[UNVERIFIED]` | Run B0 1024/4-step versus B 768/4-step and stock versus FP16-safe VAE. | Same-seed P50/P95, stages, VRAM, warnings, failures, and image samples. | L4 access and model weights. |
| 9 | `[UNVERIFIED]` | Run clean Python 3.11 resolver and `pip check` on L4. | Full `model_server/requirements.txt` installs in one command and `pip check` exits 0. | L4 access and multi-GB dependencies. |
