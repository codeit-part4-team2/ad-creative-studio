from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, RLock
from typing import Generic, TypeVar


KeyT = TypeVar("KeyT")
ValueT = TypeVar("ValueT")


@dataclass(slots=True)
class _Entry(Generic[ValueT]):
    value: ValueT
    expires_at: float


@dataclass(slots=True)
class _Pending:
    event: Event
    error: BaseException | None = None


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
        self._pending: dict[KeyT, _Pending] = {}
        self._lock = RLock()

    def get_or_create(
        self, key: KeyT, factory: Callable[[], ValueT]
    ) -> tuple[ValueT, bool]:
        while True:
            with self._lock:
                now = self._clock()
                entry = self._entries.get(key)
                if entry is not None and entry.expires_at > now:
                    self._entries.move_to_end(key)
                    return entry.value, True
                if entry is not None:
                    del self._entries[key]

                pending = self._pending.get(key)
                if pending is None:
                    pending = _Pending(event=Event())
                    self._pending[key] = pending
                    break

            pending.event.wait()
            if pending.error is not None:
                raise pending.error

        try:
            value = factory()
        except BaseException as exc:
            with self._lock:
                current = self._pending.get(key)
                if current is pending:
                    pending.error = exc
                    del self._pending[key]
                    pending.event.set()
            raise

        with self._lock:
            self._entries[key] = _Entry(
                value=value,
                expires_at=self._clock() + self._ttl_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
            current = self._pending.get(key)
            if current is pending:
                del self._pending[key]
                pending.event.set()
            return value, False
