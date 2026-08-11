"""Durable replay suppression for Time posts."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from homeassistant.helpers.storage import Store

from .const import DEDUPE_MAX_IDS, DEDUPE_TTL_SECONDS, DOMAIN


class StoragePort(Protocol):
    async def async_load(self) -> Any: ...

    async def async_save(self, data: Any) -> None: ...


class DurableDedupe:
    """Atomically check, prune, add, and save IDs before publication."""

    def __init__(
        self,
        store: StoragePort,
        *,
        now: Callable[[], float] = time.time,
        ttl_seconds: int = DEDUPE_TTL_SECONDS,
        max_ids: int = DEDUPE_MAX_IDS,
    ) -> None:
        self._store = store
        self._now = now
        self._ttl_seconds = ttl_seconds
        self._max_ids = max_ids
        self._lock = asyncio.Lock()
        self._entries: dict[str, float] | None = None

    async def async_check_and_mark(self, post_id: str) -> bool:
        """Return true only after a new id has been saved successfully."""

        if not post_id:
            return False
        async with self._lock:
            await self._async_ensure_loaded()
            assert self._entries is not None
            now = self._now()
            cutoff = now - self._ttl_seconds
            self._entries = {
                key: timestamp for key, timestamp in self._entries.items() if timestamp >= cutoff
            }
            if post_id in self._entries:
                return False
            candidate = {**self._entries, post_id: now}
            ordered = sorted(candidate.items(), key=lambda item: item[1], reverse=True)
            candidate = dict(ordered[: self._max_ids])
            await self._store.async_save({"entries": candidate})
            self._entries = candidate
            return True

    async def _async_ensure_loaded(self) -> None:
        if self._entries is not None:
            return
        loaded = await self._store.async_load()
        entries = loaded.get("entries") if isinstance(loaded, Mapping) else None
        if not isinstance(entries, Mapping):
            self._entries = {}
            return
        now = self._now()
        valid: dict[str, float] = {}
        for key, value in entries.items():
            if (
                not isinstance(key, str)
                or isinstance(value, bool)
                or not isinstance(value, int | float)
            ):
                continue
            try:
                timestamp = float(value)
            except OverflowError, TypeError, ValueError:
                continue
            if not math.isfinite(timestamp) or timestamp > now:
                continue
            valid[key] = timestamp
        self._entries = valid


def create_dedupe(hass: Any, entry_id: str) -> DurableDedupe:
    """Create an entry-private, atomic Home Assistant Store."""

    store: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"{DOMAIN}.{entry_id}.dedupe",
        private=True,
        atomic_writes=True,
    )
    return DurableDedupe(store)


async def async_remove_dedupe(hass: Any, entry_id: str) -> None:
    """Remove all local replay state for a deleted ConfigEntry."""

    store: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"{DOMAIN}.{entry_id}.dedupe",
        private=True,
        atomic_writes=True,
    )
    await store.async_remove()
