# Known Issues

| Status | Issue | Reproduction | Impact | Evidence |
|---|---|---|---|---|
| `[INFERRED]` | The original `numpy==2.2.6` conflict is repaired locally with `numpy==2.3.5`, but a clean L4 install is not rerun yet. | Run clean Python 3.11 `pip install -r model_server/requirements.txt` and `pip check` on the L4 VM. | Fresh environment reproducibility is not yet externally confirmed. | Semantic regression test passes; large clean install intentionally not downloaded locally. |
| `[VERIFIED]` | Diffusers emits empty-list dtype warnings during IP-Adapter/VAE internal casts. | Load the previous quality or stock-fast path with Diffusers 0.39.0. | No observed image failure; warning text reports `[]`, so no retained FP32 modules are named. | Exact messages supplied by serving owner; Diffusers source path inspected. |
| `[UNVERIFIED]` | The new fast FP16-safe VAE has not run on L4. | Repeat 768/4-step with the current branch and same seed as the stock-VAE report. | Warning removal, latency, VRAM, and small visual differences are not established. | Local loader contract test passes; no local model weights were downloaded. |
| `[UNVERIFIED]` | B/C/D fast results were supplied as a chat report without original JSON or resolution metadata. | Compare benchmark response files against `docs/L4_BENCHMARK_CHECKLIST.md`. | Cannot attribute the reported speed specifically to 768 or bind it to an exact commit. | Reported values are recorded in the handoff; B0 and metadata remain missing. |
