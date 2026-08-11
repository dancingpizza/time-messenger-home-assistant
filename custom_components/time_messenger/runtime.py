"""Per-entry supervised listener lifecycle."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Callable
from typing import Any

from homeassistant.helpers import issue_registry as ir

from .api.exceptions import (
    AuthError,
    ProtocolError,
    RateLimitError,
    TransientError,
    UnsupportedCapability,
)
from .api.websocket import TimeWebSocketClient, release_time_session
from .const import DOMAIN, HEALTHY_CONNECTION_SECONDS, MAX_RETRY_DELAY, RECONNECT_CAPS
from .models import CanonicalPost
from .pipeline import MessagePipeline


class TimeMessengerRuntime:
    """Own exactly one generation-guarded listener task for a ConfigEntry."""

    def __init__(
        self,
        hass: Any,
        entry: Any,
        websocket: TimeWebSocketClient,
        pipeline: MessagePipeline,
        *,
        owned_session: Any | None = None,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._websocket = websocket
        self._pipeline = pipeline
        self._owned_session = owned_session
        self._random_uniform = random_uniform
        self._generation = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def task(self) -> asyncio.Task[None] | None:
        return self._task

    async def async_start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._generation += 1
        generation = self._generation
        self._task = self._hass.async_create_task(
            self._async_supervise(generation),
            f"time_messenger_{self._entry.entry_id}",
        )

    async def async_stop(self) -> None:
        self._generation += 1
        await self._websocket.async_close()
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def async_unload(self) -> None:
        """Stop listener and close the entry-owned network session."""

        await self.async_stop()
        if self._owned_session is not None:
            release_time_session(self._owned_session)

    def _alive(self, generation: int) -> bool:
        return generation == self._generation

    async def _async_process(self, post: CanonicalPost, generation: int) -> None:
        if self._alive(generation):
            await self._pipeline.async_process(post)

    async def _async_supervise(self, generation: int) -> None:
        attempt = 0
        while self._alive(generation):
            delay: float | None = None
            try:
                healthy_for = await self._websocket.async_listen(
                    lambda post: self._async_process(post, generation),
                    lambda: self._alive(generation),
                )
                if healthy_for >= HEALTHY_CONNECTION_SECONDS:
                    attempt = 0
            except asyncio.CancelledError:
                raise
            except AuthError:
                if self._alive(generation):
                    await self._entry.async_start_reauth(self._hass)
                return
            except ProtocolError, UnsupportedCapability:
                if self._alive(generation):
                    ir.async_create_issue(
                        self._hass,
                        DOMAIN,
                        f"unsupported_tenant_{self._entry.entry_id}",
                        is_fixable=False,
                        is_persistent=True,
                        severity=ir.IssueSeverity.ERROR,
                        translation_key="unsupported_tenant",
                    )
                return
            except RateLimitError as err:
                if err.retry_after is not None and math.isfinite(err.retry_after):
                    delay = min(MAX_RETRY_DELAY, max(1.0, err.retry_after))
            except TransientError:
                pass
            except Exception:
                pass
            if not self._alive(generation):
                return
            cap = RECONNECT_CAPS[min(attempt, len(RECONNECT_CAPS) - 1)]
            jitter = self._random_uniform(0.0, cap)
            attempt += 1
            await asyncio.sleep(max(1.0, jitter, delay or 0.0))
