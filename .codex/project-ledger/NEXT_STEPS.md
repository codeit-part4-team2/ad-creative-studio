# Next Steps

| Priority | Status | Action | Acceptance evidence | Blocker |
|---|---|---|---|---|
| 1 | `[VERIFIED]` | Review the 2026-08-10 design and plan. | User approval and committed design/plan. | None |
| 2 | `[VERIFIED]` | Fix dependency pins and add semantic compatibility regression coverage. | Focused test and full local gate pass. | Clean L4 environment resolution remains external. |
| 3 | `[VERIFIED]` | Add configurable 768 fast background, 1024 normalization, and explicit size metadata. | 175 tests plus Ruff, compileall, pip check, and diff check pass. | L4 timing and visual quality remain external. |
| 4 | `[UNVERIFIED]` | Reconcile the locally verified Shorts worktree with the model result contract. | Local API/browser E2E using a persisted model result. | None |
| 5 | `[UNVERIFIED]` | Ask serving owner to rerun clean install and B0/B/C/D/E matrix. | Resolver succeeds; benchmark JSON and image samples are returned. | L4 access and multi-GB dependencies. |
