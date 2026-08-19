from __future__ import annotations

import argparse
import json
import math
import statistics
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _rounded(value: float) -> float:
    return round(value, 6)


def _nearest_rank(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summarize_runs(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not runs or any(
        run.get("status", "done") != "done" or run.get("gen_time_sec") is None
        for run in runs
    ):
        raise ValueError("benchmark summary requires successful inference runs")

    latencies = [float(run["gen_time_sec"]) for run in runs]
    stage_names = sorted(
        {
            stage
            for run in runs
            for stage in run.get("stage_times_sec", {}).keys()
        }
    )
    stage_medians = {
        stage: _rounded(
            statistics.median(
                float(run["stage_times_sec"][stage])
                for run in runs
                if stage in run.get("stage_times_sec", {})
            )
        )
        for stage in stage_names
    }
    configuration_keys = (
        "model_profile",
        "num_inference_steps",
        "output_format",
        "background_width",
        "background_height",
        "output_width",
        "output_height",
    )
    configurations = {
        tuple(run.get(key) for key in configuration_keys)
        for run in runs
    }
    if len(configurations) != 1:
        raise ValueError("benchmark summary requires one consistent configuration")
    configuration_values = configurations.pop()
    return {
        "runs": len(runs),
        "latency_sec": {
            "min": _rounded(min(latencies)),
            "p50": _rounded(statistics.median(latencies)),
            "p95": _rounded(_nearest_rank(latencies, 0.95)),
            "max": _rounded(max(latencies)),
        },
        "stage_median_sec": stage_medians,
        "configuration": dict(zip(configuration_keys, configuration_values)),
    }


def post_json(url: str, payload: Mapping[str, Any], *, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure warm model-server latency and stage timings."
    )
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8001/infer",
    )
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.warmup < 0 or args.runs <= 0:
        raise SystemExit("--warmup must be non-negative and --runs must be positive")
    payload = json.loads(args.payload.read_text(encoding="utf-8"))

    for _ in range(args.warmup):
        warmup = post_json(args.url, payload, timeout=args.timeout)
        if warmup.get("status") != "done":
            raise SystemExit(f"warmup failed: {warmup.get('error_message', 'unknown')}")

    results = [
        post_json(args.url, payload, timeout=args.timeout)
        for _ in range(args.runs)
    ]
    print(json.dumps(summarize_runs(results), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
