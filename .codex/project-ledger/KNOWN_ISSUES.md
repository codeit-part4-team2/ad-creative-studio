# Known Issues

| Status | Issue | Reproduction | Impact | Evidence |
|---|---|---|---|---|
| `[INFERRED]` | The original `numpy==2.2.6` conflict is repaired locally with `numpy==2.3.5`, but a clean L4 install is not rerun yet. | Run clean Python 3.11 `pip install -r model_server/requirements.txt` and `pip check` on the L4 VM. | Fresh environment reproducibility is not yet externally confirmed. | Semantic regression test passes; large clean install intentionally not downloaded locally. |
| `[UNVERIFIED]` | UNet dtype warning may be benign retained-FP32 behavior. | Exact warning text and stack location have not been supplied. | Do not change dtype handling until the original warning is captured. | Current loader already supplies CUDA FP16 to pipeline, ControlNet, and VAE. |
| `[VERIFIED]` | PR #15 lacks fast-profile L4 measurements, including the new 768 background. | Only `quality_regenerate` 30-step experiment A has been reported. | Final default latency and quality are not established. | Serving benchmark report dated 2026-08-10 |
