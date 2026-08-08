from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class StageTimings:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.perf_counter,
        synchronize: Callable[[], None] | None = None,
    ) -> None:
        self._clock = clock
        self._synchronize = synchronize
        self._elapsed: dict[str, float] = {}

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        if self._synchronize is not None:
            self._synchronize()
        started_at = self._clock()
        try:
            yield
        finally:
            if self._synchronize is not None:
                self._synchronize()
            elapsed = self._clock() - started_at
            self._elapsed[name] = self._elapsed.get(name, 0.0) + elapsed

    def as_dict(self) -> dict[str, float]:
        return {name: round(value, 6) for name, value in self._elapsed.items()}
