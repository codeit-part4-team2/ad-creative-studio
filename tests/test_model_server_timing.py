from __future__ import annotations

from collections import deque

from model_server.timing import StageTimings


def test_measure_records_elapsed_seconds_and_synchronizes_boundaries() -> None:
    values = deque([10.0, 10.25])
    sync_calls: list[str] = []
    timings = StageTimings(
        clock=values.popleft,
        synchronize=lambda: sync_calls.append("sync"),
    )

    with timings.measure("generate"):
        pass

    assert timings.as_dict() == {"generate": 0.25}
    assert sync_calls == ["sync", "sync"]


def test_repeated_stage_measurements_accumulate() -> None:
    values = deque([1.0, 1.1, 2.0, 2.4])
    timings = StageTimings(clock=values.popleft)

    with timings.measure("save"):
        pass
    with timings.measure("save"):
        pass

    assert timings.as_dict()["save"] == 0.5
