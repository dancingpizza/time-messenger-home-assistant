"""Per-entry supervised listener lifecycle."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .api.exceptions import (
    AuthError,
    ProtocolError,
    RateLimitError,
    TransientError,
    UnsupportedCapability,
)
from .api.websocket import TimeWebSocketClient, release_time_session
from .const import (
    AUTH_HEALTH_CHECK_INTERVAL,
    AUTH_HEALTH_CHECK_JITTER_RATIO,
    DOMAIN,
    HEALTHY_CONNECTION_SECONDS,
    MAX_RETRY_DELAY,
    RECONNECT_CAPS,
    keep_online_issue_id,
)
from .models import CanonicalPost
from .pipeline import MessagePipeline
from .schedule import KeepOnlineSchedule

_SCHEDULE_RECHECK_SECONDS = 60.0


class TimeMessengerRuntime:
    """Own generation-guarded listener, auth health, and presence tasks."""

    def __init__(
        self,
        hass: Any,
        entry: Any,
        websocket: TimeWebSocketClient,
        pipeline: MessagePipeline,
        *,
        owned_session: Any | None = None,
        health_check: Callable[[], Awaitable[None]] | None = None,
        health_check_interval: float = AUTH_HEALTH_CHECK_INTERVAL,
        keep_online: Callable[[], Awaitable[bool]] | None = None,
        keep_online_schedule: KeepOnlineSchedule | None = None,
        keep_online_interval: float | None = None,
        now: Callable[[], datetime] = dt_util.now,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        keep_online_parts = (keep_online, keep_online_schedule, keep_online_interval)
        if any(part is None for part in keep_online_parts) != all(
            part is None for part in keep_online_parts
        ):
            raise ValueError("keep-online callback, schedule, and interval belong together")
        if keep_online_interval is not None and (
            not math.isfinite(keep_online_interval) or keep_online_interval <= 0
        ):
            raise ValueError("keep-online interval must be finite and positive")
        self._hass = hass
        self._entry = entry
        self._websocket = websocket
        self._pipeline = pipeline
        self._owned_session = owned_session
        self._health_check = health_check
        self._health_check_interval = health_check_interval
        self._keep_online = keep_online
        self._keep_online_schedule = keep_online_schedule
        self._keep_online_interval = keep_online_interval
        self._now = now
        self._random_uniform = random_uniform
        self._generation = 0
        self._task: asyncio.Task[None] | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._keep_online_task: asyncio.Task[None] | None = None

    @property
    def task(self) -> asyncio.Task[None] | None:
        return self._task

    @property
    def health_task(self) -> asyncio.Task[None] | None:
        return self._health_task

    @property
    def keep_online_task(self) -> asyncio.Task[None] | None:
        return self._keep_online_task

    async def async_start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._generation += 1
        generation = self._generation
        if self._health_check is not None:
            self._health_task = self._hass.async_create_task(
                self._async_health_loop(generation),
                f"time_messenger_{self._entry.entry_id}_auth_health",
            )
        if self._keep_online is not None:
            self._keep_online_task = self._hass.async_create_task(
                self._async_keep_online_loop(generation),
                f"time_messenger_{self._entry.entry_id}_keep_online",
            )
        self._task = self._hass.async_create_task(
            self._async_supervise(generation),
            f"time_messenger_{self._entry.entry_id}",
        )

    async def async_stop(self) -> None:
        self._generation += 1
        tasks = tuple(
            task
            for task in (self._task, self._health_task, self._keep_online_task)
            if task is not None
        )
        self._task = None
        self._health_task = None
        self._keep_online_task = None
        current = asyncio.current_task()
        pending = tuple(task for task in tasks if task is not current)
        for task in pending:
            if not task.done():
                task.cancel()
        await self._websocket.async_close()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

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

    async def _async_surface_auth_failure(self, generation: int) -> None:
        """Invalidate both loops and let setup expose auth failure in the UI."""

        if not self._alive(generation):
            return
        self._generation += 1
        failure_generation = self._generation
        current = asyncio.current_task()
        for task in (self._task, self._health_task, self._keep_online_task):
            if task is not None and task is not current and not task.done():
                task.cancel()
        try:
            await self._websocket.async_close()
        finally:
            # Unload may invalidate the generation while socket close yields.
            # In that case it owns cleanup and no UI flow may outlive the entry.
            if self._generation == failure_generation:
                # Never reset a form while the user is already repairing this
                # entry. The active flow has its own red card and Repairs issue.
                active_flow = any(
                    self._entry.async_get_active_flows(
                        self._hass, {SOURCE_REAUTH, SOURCE_RECONFIGURE}
                    )
                )
                if not active_flow:
                    # A direct async_start_reauth() creates the Repairs action
                    # but leaves this ConfigEntry in LOADED. Going through the
                    # public reload path makes async_setup_entry raise
                    # ConfigEntryAuthFailed, so HA both starts reauth and marks
                    # the integration card red.
                    self._hass.config_entries.async_schedule_reload(self._entry.entry_id)

    def _next_health_check_delay(self) -> float:
        jitter = self._health_check_interval * AUTH_HEALTH_CHECK_JITTER_RATIO
        return max(
            0.001,
            self._random_uniform(
                self._health_check_interval - jitter,
                self._health_check_interval + jitter,
            ),
        )

    async def _async_health_loop(self, generation: int) -> None:
        """Periodically validate credentials without disrupting a healthy socket."""

        assert self._health_check is not None
        while self._alive(generation):
            await asyncio.sleep(self._next_health_check_delay())
            if not self._alive(generation):
                return
            try:
                await self._health_check()
            except asyncio.CancelledError:
                raise
            except AuthError:
                await self._async_surface_auth_failure(generation)
                return
            except Exception:
                # Only an explicit authentication rejection is evidence that the
                # user must act. Network, rate-limit, and protocol failures get
                # another health-check attempt while the push connection stays up.
                continue

    async def _async_keep_online_loop(self, generation: int) -> None:
        """Set online only inside the configured Home Assistant-local window."""

        assert self._keep_online is not None
        assert self._keep_online_schedule is not None
        assert self._keep_online_interval is not None
        schedule = self._keep_online_schedule
        issue_id = keep_online_issue_id(self._entry.entry_id)
        while self._alive(generation):
            current = self._now()
            if not schedule.is_active(current):
                # Re-evaluate at least once a minute so timezone or wall-clock
                # changes cannot leave a long monotonic sleep on the old schedule.
                delay = min(
                    _SCHEDULE_RECHECK_SECONDS,
                    schedule.seconds_until_next_start(current),
                )
                await asyncio.sleep(max(0.001, delay))
                continue

            delay = self._keep_online_interval
            try:
                request_sent = await self._keep_online()
            except asyncio.CancelledError:
                raise
            except AuthError:
                await self._async_surface_auth_failure(generation)
                return
            except UnsupportedCapability, ProtocolError:
                if self._alive(generation):
                    # Presence is optional. Keep message delivery and auth health
                    # alive, but make a permanently stopped keeper visible.
                    ir.async_create_issue(
                        self._hass,
                        DOMAIN,
                        issue_id,
                        is_fixable=False,
                        is_persistent=True,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="keep_online_unavailable",
                    )
                return
            except RateLimitError as err:
                if err.retry_after is not None and math.isfinite(err.retry_after):
                    delay = max(delay, min(MAX_RETRY_DELAY, max(1.0, err.retry_after)))
            except TransientError:
                pass
            except Exception:
                # An optional presence failure must never kill message delivery.
                # Retry on the next configured cadence without exposing details.
                pass
            else:
                if request_sent and self._alive(generation):
                    ir.async_delete_issue(self._hass, DOMAIN, issue_id)

            if not self._alive(generation):
                return
            # Sleeping may cross the exclusive end boundary; the next iteration
            # rechecks the window before any request. Keeping the full delay also
            # preserves cadence/Retry-After if the request itself crossed into
            # a short inactive gap.
            await asyncio.sleep(max(0.001, delay))

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
                await self._async_surface_auth_failure(generation)
                return
            except ProtocolError, UnsupportedCapability:
                if self._alive(generation):
                    self._generation += 1
                    for background_task in (self._health_task, self._keep_online_task):
                        if background_task is not None and not background_task.done():
                            background_task.cancel()
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
