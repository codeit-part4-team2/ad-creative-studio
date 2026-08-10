# Next Steps

| Priority | Status | Action | Acceptance evidence | Blocker |
|---|---|---|---|---|
| 1 | `[VERIFIED]` | Review the 2026-08-10 design. | User approval of the written specification. | None |
| 2 | `[UNVERIFIED]` | Write the TDD implementation plan. | Plan self-review passes with no placeholders or scope gaps. | Written-spec approval |
| 3 | `[UNVERIFIED]` | Fix dependency pins and add semantic compatibility regression coverage. | Clean Python 3.11 resolution and `pip check`. | Plan approval |
| 4 | `[UNVERIFIED]` | Add configurable 768 fast background and 1024 output normalization. | Focused tests, full regression, then L4 benchmark. | Plan approval and L4 access for final timing |
| 5 | `[UNVERIFIED]` | Reconcile the locally verified Shorts worktree with the model result contract. | Local API/browser E2E using a persisted model result. | Model contract implementation |
