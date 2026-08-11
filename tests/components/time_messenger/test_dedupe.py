"""Tests for persistent replay suppression."""

import math
from typing import Any

import pytest

from custom_components.time_messenger.dedupe import DurableDedupe


class MemoryStore:
    def __init__(self, data: Any = None, *, fail: bool = False) -> None:
        self.data = data
        self.fail = fail

    async def async_load(self) -> Any:
        return self.data

    async def async_save(self, data: Any) -> None:
        if self.fail:
            raise OSError("disk unavailable")
        self.data = data


async def test_duplicate_survives_new_dedupe_instance() -> None:
    store = MemoryStore()
    first = DurableDedupe(store, now=lambda: 1000)
    assert await first.async_check_and_mark("p1") is True
    restarted = DurableDedupe(store, now=lambda: 1001)
    assert await restarted.async_check_and_mark("p1") is False


async def test_entries_expire_after_24_hours() -> None:
    store = MemoryStore({"entries": {"p1": 100.0}})
    dedupe = DurableDedupe(store, now=lambda: 100.0 + 86401)
    assert await dedupe.async_check_and_mark("p1") is True


async def test_store_is_capped_to_newest_ids() -> None:
    now = 0.0
    store = MemoryStore()
    dedupe = DurableDedupe(store, now=lambda: now, ttl_seconds=100, max_ids=2)
    for post_id in ("p1", "p2", "p3"):
        now += 1
        assert await dedupe.async_check_and_mark(post_id) is True
    assert set(store.data["entries"]) == {"p2", "p3"}


async def test_storage_failure_prevents_success() -> None:
    store = MemoryStore(fail=True)
    dedupe = DurableDedupe(store, now=lambda: 1000)
    with pytest.raises(OSError):
        await dedupe.async_check_and_mark("p1")
    store.fail = False
    assert await dedupe.async_check_and_mark("p1") is True


@pytest.mark.parametrize(
    "corrupt",
    [True, math.nan, math.inf, -math.inf, 10**1000, object(), "not-a-number", 1001.0],
)
async def test_corrupt_or_future_loaded_timestamp_is_discarded(corrupt: object) -> None:
    store = MemoryStore({"entries": {"p1": corrupt, "valid": 999.0}})
    dedupe = DurableDedupe(store, now=lambda: 1000.0)
    assert await dedupe.async_check_and_mark("p1") is True
    assert set(store.data["entries"]) == {"valid", "p1"}
