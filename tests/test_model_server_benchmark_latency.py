from __future__ import annotations

from tools.benchmark_latency import parse_args, summarize_runs


def test_summarize_runs_reports_nearest_rank_p95_and_stage_medians() -> None:
    summary = summarize_runs(
        [
            {
                "gen_time_sec": value,
                "stage_times_sec": {"generate": value - 0.2},
                "model_profile": "fast_composite",
                "num_inference_steps": 4,
                "background_size": 768,
                "output_size": 1024,
            }
            for value in [1.0, 2.0, 3.0, 4.0, 5.0]
        ]
    )

    assert summary == {
        "runs": 5,
        "latency_sec": {
            "min": 1.0,
            "p50": 3.0,
            "p95": 5.0,
            "max": 5.0,
        },
        "stage_median_sec": {"generate": 2.8},
        "configuration": {
            "model_profile": "fast_composite",
            "num_inference_steps": 4,
            "background_size": 768,
            "output_size": 1024,
        },
    }


def test_summarize_runs_rejects_mixed_configurations() -> None:
    runs = [
        {
            "gen_time_sec": 1.0,
            "model_profile": "fast_composite",
            "num_inference_steps": 4,
            "background_size": 768,
            "output_size": 1024,
        },
        {
            "gen_time_sec": 1.1,
            "model_profile": "fast_composite",
            "num_inference_steps": 4,
            "background_size": 1024,
            "output_size": 1024,
        },
    ]

    try:
        summarize_runs(runs)
    except ValueError as exc:
        assert "configuration" in str(exc)
    else:
        raise AssertionError("mixed benchmark configurations must be rejected")


def test_summarize_runs_rejects_failed_or_empty_results() -> None:
    try:
        summarize_runs([])
    except ValueError as exc:
        assert "successful" in str(exc)
    else:
        raise AssertionError("empty benchmark must be rejected")

    try:
        summarize_runs([{"status": "failed"}])
    except ValueError as exc:
        assert "successful" in str(exc)
    else:
        raise AssertionError("failed benchmark result must be rejected")


def test_benchmark_defaults_to_model_server_port(monkeypatch, tmp_path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["benchmark_latency.py", "--payload", str(payload)],
    )

    args = parse_args()

    assert args.url == "http://127.0.0.1:8001/infer"
