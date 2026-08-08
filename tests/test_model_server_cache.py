from __future__ import annotations

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
