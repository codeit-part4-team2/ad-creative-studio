from __future__ import annotations

import threading

from model_server.cache import TTLCache


def test_get_or_create_reuses_value_before_expiry() -> None:
    now = [100.0]
    cache: TTLCache[str, object] = TTLCache(
        max_entries=2,
        ttl_seconds=10.0,
        clock=lambda: now[0],
    )
    calls: list[str] = []

    first, first_hit = cache.get_or_create("product", lambda: calls.append("run") or object())
    second, second_hit = cache.get_or_create("product", lambda: calls.append("run") or object())

    assert first is second
    assert first_hit is False
    assert second_hit is True
    assert calls == ["run"]


def test_get_or_create_refreshes_expired_value() -> None:
    now = [100.0]
    cache: TTLCache[str, int] = TTLCache(
        max_entries=2,
        ttl_seconds=5.0,
        clock=lambda: now[0],
    )

    first, _ = cache.get_or_create("product", lambda: 1)
    now[0] = 106.0
    second, hit = cache.get_or_create("product", lambda: 2)

    assert first == 1
    assert second == 2
    assert hit is False


def test_cache_evicts_least_recently_used_entry() -> None:
    cache: TTLCache[str, int] = TTLCache(max_entries=2, ttl_seconds=60.0)
    cache.get_or_create("a", lambda: 1)
    cache.get_or_create("b", lambda: 2)
    cache.get_or_create("a", lambda: 99)
    cache.get_or_create("c", lambda: 3)

    value, hit = cache.get_or_create("b", lambda: 20)

    assert value == 20
    assert hit is False


def test_cache_builds_different_keys_concurrently() -> None:
    cache: TTLCache[str, int] = TTLCache(max_entries=2, ttl_seconds=60.0)
    first_started = threading.Event()
    second_started = threading.Event()
    release = threading.Event()

    def build_first() -> int:
        first_started.set()
        release.wait(timeout=2)
        return 1

    def build_second() -> int:
        second_started.set()
        release.wait(timeout=2)
        return 2

    first = threading.Thread(
        target=cache.get_or_create,
        args=("first", build_first),
    )
    second = threading.Thread(
        target=cache.get_or_create,
        args=("second", build_second),
    )

    first.start()
    try:
        assert first_started.wait(timeout=1)
        second.start()
        assert second_started.wait(timeout=1)
    finally:
        release.set()
        first.join(timeout=2)
        if second.ident is not None:
            second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()


def test_cache_coalesces_concurrent_builds_for_the_same_key() -> None:
    cache: TTLCache[str, object] = TTLCache(max_entries=2, ttl_seconds=60.0)
    factory_started = threading.Event()
    release = threading.Event()
    calls = 0
    calls_lock = threading.Lock()
    results: list[tuple[object, bool]] = []

    def build() -> object:
        nonlocal calls
        with calls_lock:
            calls += 1
        factory_started.set()
        release.wait(timeout=2)
        return object()

    def get_value() -> None:
        results.append(cache.get_or_create("product", build))

    first = threading.Thread(target=get_value)
    second = threading.Thread(target=get_value)
    first.start()
    assert factory_started.wait(timeout=1)
    second.start()
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert calls == 1
    assert len(results) == 2
    assert results[0][0] is results[1][0]
    assert sorted(hit for _, hit in results) == [False, True]
