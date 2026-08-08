from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar


KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


@dataclass(slots=True)
class _Entry(Generic[ValueT]):
    value: ValueT
    expires_at: float


class TTLCache(Generic[KeyT, ValueT]):
    def __init__(
        self,
        *,
        max_entries: int,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[KeyT, _Entry[ValueT]] = OrderedDict()
        self._lock = RLock()

    def get_or_create(
        self, key: KeyT, factory: Callable[[], ValueT]
    ) -> tuple[ValueT, bool]:
        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                self._entries.move_to_end(key)
                return entry.value, True
            if entry is not None:
                del self._entries[key]

            value = factory()
            self._entries[key] = _Entry(
                value=value,
                expires_at=self._clock() + self._ttl_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
            return value, False
