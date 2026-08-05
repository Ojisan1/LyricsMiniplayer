"""Tests for bounded LRU cache eviction."""

from core.cache import BoundedMemoryCache


def test_get_missing_returns_none():
    cache = BoundedMemoryCache(max_entries=3, max_bytes=100)
    assert cache.get("missing") is None


def test_put_and_get_updates_lru_order():
    cache = BoundedMemoryCache(max_entries=2, max_bytes=100)
    cache.put("a", "A", 10)
    cache.put("b", "B", 10)
    assert cache.get("a") == "A"  # touches a
    cache.put("c", "C", 10)  # should evict b (least recently used)
    assert cache.get("b") is None
    assert cache.get("a") == "A"
    assert cache.get("c") == "C"
    assert len(cache) == 2


def test_evicts_by_byte_budget():
    cache = BoundedMemoryCache(max_entries=10, max_bytes=30)
    cache.put("a", "A", 20)
    cache.put("b", "B", 20)  # needs room; evicts a
    assert cache.get("a") is None
    assert cache.get("b") == "B"
    assert len(cache) == 1


def test_rejects_single_item_larger_than_budget():
    cache = BoundedMemoryCache(max_entries=10, max_bytes=50)
    cache.put("huge", "X", 51)
    assert len(cache) == 0
    assert cache.get("huge") is None


def test_replace_same_key_updates_size():
    cache = BoundedMemoryCache(max_entries=5, max_bytes=100)
    cache.put("a", "old", 40)
    cache.put("a", "new", 10)
    assert cache.get("a") == "new"
    assert len(cache) == 1
    # Remaining budget should allow another 90-byte entry.
    cache.put("b", "B", 90)
    assert cache.get("a") == "new"
    assert cache.get("b") == "B"
