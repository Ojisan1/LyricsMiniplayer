"""Bounded in-memory LRU cache for lyrics and artwork."""

from __future__ import annotations

from collections import OrderedDict
from typing import Generic, TypeVar

from core.limits import MAX_CACHE_BYTES, MAX_CACHE_ENTRIES

T = TypeVar("T")


class BoundedMemoryCache(Generic[T]):
    """LRU cache capped by entry count and approximate payload bytes."""

    def __init__(
        self,
        *,
        max_entries: int = MAX_CACHE_ENTRIES,
        max_bytes: int = MAX_CACHE_BYTES,
    ) -> None:
        self._max_entries = max(1, max_entries)
        self._max_bytes = max(1, max_bytes)
        self._items: OrderedDict[object, tuple[T, int]] = OrderedDict()
        self._total_bytes = 0

    def get(self, key: object) -> T | None:
        item = self._items.get(key)
        if item is None:
            return None
        self._items.move_to_end(key)
        return item[0]

    def put(self, key: object, value: T, size_bytes: int) -> None:
        size = max(0, int(size_bytes))
        if size > self._max_bytes:
            # Single item larger than the budget — do not cache it.
            return
        existing = self._items.pop(key, None)
        if existing is not None:
            self._total_bytes -= existing[1]
        while self._items and (
            len(self._items) >= self._max_entries
            or self._total_bytes + size > self._max_bytes
        ):
            _, (_, old_size) = self._items.popitem(last=False)
            self._total_bytes -= old_size
        self._items[key] = (value, size)
        self._total_bytes += size

    def __len__(self) -> int:
        return len(self._items)


# Shared across lyrics and artwork so the combined budget is enforced.
media_cache: BoundedMemoryCache[object] = BoundedMemoryCache()
