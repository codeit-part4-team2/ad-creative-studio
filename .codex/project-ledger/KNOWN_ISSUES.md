# Known Issues

| Status | Issue | Reproduction | Impact | Evidence |
|---|---|---|---|---|
| `[VERIFIED]` | `numpy==2.2.6` conflicts with `rembg[gpu]==2.0.76`, which requires NumPy 2.3 or newer. | Clean Python 3.11 `pip install -r model_server/requirements.txt` on the L4 VM. | Fresh environment installation is not reproducible. | Serving benchmark report and current requirements file |
| `[UNVERIFIED]` | UNet dtype warning may be benign retained-FP32 behavior. | Exact warning text and stack location have not been supplied. | Do not change dtype handling until the original warning is captured. | Current loader already supplies CUDA FP16 to pipeline, ControlNet, and VAE. |
| `[VERIFIED]` | PR #15 lacks fast-profile L4 measurements. | Only `quality_regenerate` 30-step experiment A has been reported. | Final default latency and quality are not established. | Serving benchmark report dated 2026-08-10 |
