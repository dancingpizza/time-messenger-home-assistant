"""Tests for the single supervised listener and lifecycle."""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.helpers import issue_registry as ir

from custom_components.time_messenger.api.exceptions import (
    AuthError,
    ProtocolError,
    RateLimitError,
    TransientError,
    UnsupportedCapability,
)
from custom_components.time_messenger.runtime import TimeMessengerRuntime
from custom_components.time_messenger.schedule import KeepOnlineSchedule

MOSCOW = ZoneInfo("Europe/Moscow")
MONDAY_MORNING = datetime(2026, 8, 17, 9, tzinfo=MOSCOW)


def workday_schedule() -> KeepOnlineSchedule:
    return KeepOnlineSchedule(["mon", "tue", "wed", "thu", "fri"], "09:00:00", "18:00:00")


class Hass:
    def __init__(self) -> None:
        self.config_entries = SimpleNamespace(async_schedule_reload=Mock())

    def async_create_task(
        self, coroutine: object, _name: str, **_kwargs: object
    ) -> asyncio.Task[None]:
        return asyncio.create_task(coroutine)  # type: ignore[arg-type]


class BlockingWebSocket:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.closed = False
        self.calls = 0

    async def async_listen(self, _callback: object, _guard: object) -> float:
        self.calls += 1
        self.started.set()
        await asyncio.Event().wait()
        return 0

    async def async_close(self) -> None:
        self.closed = True


async def test_start_is_idempotent_and_unload_leaves_no_task() -> None:
    websocket = BlockingWebSocket()
    entry = SimpleNamespace(entry_id="entry")
    runtime = TimeMessengerRuntime(
        Hass(),
        entry,
        websocket,
        AsyncMock(),
        health_check=AsyncMock(),
        health_check_interval=3600,
    )  # type: ignore[arg-type]
    await runtime.async_start()
    await runtime.async_start()
    await websocket.started.wait()
    assert websocket.calls == 1
    task = runtime.task
    health_task = runtime.health_task
    assert task is not None
    assert health_task is not None
    await runtime.async_stop()
    assert runtime.task is None
    assert runtime.health_task is None
    assert task.done()
    assert health_task.done()
    assert websocket.closed is True


async def test_enabled_keep_online_task_is_owned_and_cancelled_with_runtime() -> None:
    websocket = BlockingWebSocket()
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        websocket,
        AsyncMock(),
        keep_online=AsyncMock(side_effect=TransientError("offline")),
        keep_online_schedule=workday_schedule(),
        keep_online_interval=3600,
        now=lambda: MONDAY_MORNING,
    )  # type: ignore[arg-type]

    await runtime.async_start()
    await websocket.started.wait()
    keep_online_task = runtime.keep_online_task
    assert keep_online_task is not None and not keep_online_task.done()

    await runtime.async_stop()

    assert runtime.keep_online_task is None
    assert keep_online_task.cancelled()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"keep_online": AsyncMock()},
        {"keep_online_schedule": workday_schedule()},
        {"keep_online_interval": 240.0},
        {
            "keep_online": AsyncMock(),
            "keep_online_schedule": workday_schedule(),
        },
    ],
)
def test_keep_online_runtime_parts_cannot_be_partially_configured(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="belong together"):
        TimeMessengerRuntime(
            Hass(),
            SimpleNamespace(entry_id="entry"),
            BlockingWebSocket(),
            AsyncMock(),
            **kwargs,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("interval", [0.0, -1.0, float("nan"), float("inf")])
def test_keep_online_interval_must_be_positive_and_finite(interval: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        TimeMessengerRuntime(
            Hass(),
            SimpleNamespace(entry_id="entry"),
            BlockingWebSocket(),
            AsyncMock(),
            keep_online=AsyncMock(),
            keep_online_schedule=workday_schedule(),
            keep_online_interval=interval,
        )  # type: ignore[arg-type]


class FailingWebSocket:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    async def async_listen(self, _callback: object, _guard: object) -> float:
        self.calls += 1
        raise self.error

    async def async_close(self) -> None:
        return None


async def test_terminal_auth_reloads_same_entry_to_surface_failure_without_retry() -> None:
    hass = Hass()
    entry = SimpleNamespace(entry_id="entry", async_get_active_flows=Mock(return_value=iter(())))
    websocket = FailingWebSocket(AuthError("expired"))
    runtime = TimeMessengerRuntime(hass, entry, websocket, AsyncMock())  # type: ignore[arg-type]
    await runtime.async_start()
    assert runtime.task is not None
    await runtime.task
    hass.config_entries.async_schedule_reload.assert_called_once_with("entry")
    assert websocket.calls == 1


async def test_health_check_runs_periodically_while_listener_is_alive() -> None:
    hass = Hass()
    entry = SimpleNamespace(entry_id="entry")
    websocket = BlockingWebSocket()
    checked_twice = asyncio.Event()
    check_count = 0

    async def health_check() -> None:
        nonlocal check_count
        check_count += 1
        if check_count == 2:
            checked_twice.set()

    runtime = TimeMessengerRuntime(
        hass,
        entry,
        websocket,
        AsyncMock(),
        health_check=health_check,
        health_check_interval=0.01,
        random_uniform=lambda _low, _high: 0.001,
    )  # type: ignore[arg-type]
    await runtime.async_start()
    await asyncio.wait_for(checked_twice.wait(), timeout=1)

    assert check_count >= 2
    assert runtime.task is not None and not runtime.task.done()
    assert runtime.health_task is not None and not runtime.health_task.done()
    hass.config_entries.async_schedule_reload.assert_not_called()
    await runtime.async_stop()


async def test_slow_health_checks_never_overlap() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def health_check() -> None:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()

    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        health_check=health_check,
        health_check_interval=0.01,
        random_uniform=lambda _low, _high: 0.001,
    )  # type: ignore[arg-type]
    await runtime.async_start()
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.01)

    assert calls == 1
    release.set()
    await runtime.async_stop()


@pytest.mark.parametrize(
    ("pick_delay", "expected"),
    [
        (lambda low, _high: low, 13.5 * 60),
        (lambda _low, high: high, 16.5 * 60),
    ],
)
def test_health_check_delay_has_ten_percent_jitter(pick_delay: object, expected: float) -> None:
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        health_check=AsyncMock(),
        health_check_interval=15 * 60,
        random_uniform=pick_delay,  # type: ignore[arg-type]
    )  # type: ignore[arg-type]

    assert runtime._next_health_check_delay() == expected


async def test_health_auth_reloads_once_and_stops_both_tasks() -> None:
    hass = Hass()
    entry = SimpleNamespace(entry_id="entry", async_get_active_flows=Mock(return_value=iter(())))
    websocket = BlockingWebSocket()
    health_check = AsyncMock(side_effect=AuthError("expired"))
    runtime = TimeMessengerRuntime(
        hass,
        entry,
        websocket,
        AsyncMock(),
        health_check=health_check,
        health_check_interval=0.01,
        random_uniform=lambda _low, _high: 0.001,
    )  # type: ignore[arg-type]
    await runtime.async_start()
    listener_task = runtime.task
    health_task = runtime.health_task
    assert listener_task is not None
    assert health_task is not None

    await asyncio.wait_for(health_task, timeout=1)
    await asyncio.gather(listener_task, return_exceptions=True)

    health_check.assert_awaited_once()
    hass.config_entries.async_schedule_reload.assert_called_once_with("entry")
    assert listener_task.done()
    assert health_task.done()


async def test_auth_failure_does_not_reset_active_reauth_flow() -> None:
    hass = Hass()
    entry = SimpleNamespace(
        entry_id="entry",
        async_get_active_flows=Mock(return_value=iter(({"flow_id": "active"},))),
    )
    websocket = FailingWebSocket(AuthError("expired"))
    runtime = TimeMessengerRuntime(hass, entry, websocket, AsyncMock())  # type: ignore[arg-type]

    await runtime.async_start()
    assert runtime.task is not None
    await runtime.task

    hass.config_entries.async_schedule_reload.assert_not_called()
    entry.async_get_active_flows.assert_called_once_with(hass, {SOURCE_REAUTH, SOURCE_RECONFIGURE})


@pytest.mark.parametrize(
    "failure",
    [TransientError("offline"), RateLimitError(0.001)],
)
async def test_retryable_health_failure_does_not_reload(failure: Exception) -> None:
    hass = Hass()
    entry = SimpleNamespace(entry_id="entry")
    websocket = BlockingWebSocket()
    recovered = asyncio.Event()
    check_count = 0

    async def health_check() -> None:
        nonlocal check_count
        check_count += 1
        if check_count == 1:
            raise failure
        recovered.set()

    runtime = TimeMessengerRuntime(
        hass,
        entry,
        websocket,
        AsyncMock(),
        health_check=health_check,
        health_check_interval=0.01,
        random_uniform=lambda _low, _high: 0.001,
    )  # type: ignore[arg-type]
    await runtime.async_start()
    await asyncio.wait_for(recovered.wait(), timeout=1)

    hass.config_entries.async_schedule_reload.assert_not_called()
    assert runtime.task is not None and not runtime.task.done()
    assert runtime.health_task is not None and not runtime.health_task.done()
    await runtime.async_stop()


async def test_unload_cancels_health_check_task() -> None:
    started = asyncio.Event()

    async def health_check() -> None:
        started.set()
        await asyncio.Event().wait()

    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        health_check=health_check,
        health_check_interval=0.01,
        random_uniform=lambda _low, _high: 0.001,
    )  # type: ignore[arg-type]
    await runtime.async_start()
    health_task = runtime.health_task
    assert health_task is not None
    await asyncio.wait_for(started.wait(), timeout=1)

    await runtime.async_unload()

    assert runtime.health_task is None
    assert health_task.cancelled()


async def test_late_health_auth_after_generation_invalidation_does_not_reload() -> None:
    hass = Hass()
    entry = SimpleNamespace(entry_id="entry")
    started = asyncio.Event()
    release = asyncio.Event()

    async def late_auth_failure() -> None:
        started.set()
        await release.wait()
        raise AuthError("expired")

    runtime = TimeMessengerRuntime(
        hass,
        entry,
        BlockingWebSocket(),
        AsyncMock(),
        health_check=late_auth_failure,
        health_check_interval=0.01,
        random_uniform=lambda _low, _high: 0.001,
    )  # type: ignore[arg-type]
    await runtime.async_start()
    health_task = runtime.health_task
    assert health_task is not None
    await asyncio.wait_for(started.wait(), timeout=1)

    runtime._generation += 1
    release.set()
    await asyncio.wait_for(health_task, timeout=1)

    hass.config_entries.async_schedule_reload.assert_not_called()
    await runtime.async_stop()


async def test_keep_online_makes_no_request_outside_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keep_online = AsyncMock(return_value=True)
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        keep_online=keep_online,
        keep_online_schedule=workday_schedule(),
        keep_online_interval=240,
        now=lambda: datetime(2026, 8, 17, 8, tzinfo=MOSCOW),
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop_after_sleep(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop_after_sleep)
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    keep_online.assert_not_awaited()
    assert sleeps == [60.0]


async def test_keep_online_calls_immediately_inside_window_and_uses_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keep_online = AsyncMock(return_value=True)
    delete_issue = Mock()
    monkeypatch.setattr(
        "custom_components.time_messenger.runtime.ir.async_delete_issue", delete_issue
    )
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        keep_online=keep_online,
        keep_online_schedule=workday_schedule(),
        keep_online_interval=240,
        now=lambda: MONDAY_MORNING,
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop_after_sleep(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop_after_sleep)
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    keep_online.assert_awaited_once()
    assert sleeps == [240]
    delete_issue.assert_called_once_with(
        runtime._hass,
        "time_messenger",
        "keep_online_unavailable_entry",
    )


async def test_suppressed_late_request_keeps_cadence_without_clearing_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delete_issue = Mock()
    monkeypatch.setattr(
        "custom_components.time_messenger.runtime.ir.async_delete_issue", delete_issue
    )
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        keep_online=AsyncMock(return_value=False),
        keep_online_schedule=workday_schedule(),
        keep_online_interval=240,
        now=lambda: MONDAY_MORNING,
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop_after_sleep(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop_after_sleep)
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    assert sleeps == [240]
    delete_issue.assert_not_called()


async def test_keep_online_keeps_full_cadence_near_window_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        keep_online=AsyncMock(side_effect=TransientError("offline")),
        keep_online_schedule=workday_schedule(),
        keep_online_interval=240,
        now=lambda: datetime(2026, 8, 17, 17, 59, tzinfo=MOSCOW),
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop_after_sleep(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop_after_sleep)
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    assert sleeps == [240]


@pytest.mark.parametrize(
    ("failure", "expected_delay"),
    [
        (TransientError("offline"), 240.0),
        (RateLimitError(30.0), 240.0),
        (RateLimitError(300.0), 300.0),
        (RuntimeError("unexpected"), 240.0),
    ],
)
async def test_keep_online_retryable_failure_waits_without_stopping_listener(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    expected_delay: float,
) -> None:
    hass = Hass()
    runtime = TimeMessengerRuntime(
        hass,
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        keep_online=AsyncMock(side_effect=failure),
        keep_online_schedule=workday_schedule(),
        keep_online_interval=240,
        now=lambda: MONDAY_MORNING,
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop_after_sleep(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop_after_sleep)
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    assert sleeps == [expected_delay]
    hass.config_entries.async_schedule_reload.assert_not_called()


async def test_request_crossing_window_end_keeps_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = datetime(2026, 8, 17, 23, 59, 58, tzinfo=MOSCOW)

    async def rate_limited_after_window_closes() -> None:
        nonlocal current
        current = datetime(2026, 8, 17, 23, 59, 59, 500_000, tzinfo=MOSCOW)
        raise RateLimitError(300)

    schedule = KeepOnlineSchedule(
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "00:00:00",
        "23:59:59",
    )
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        keep_online=rate_limited_after_window_closes,
        keep_online_schedule=schedule,
        keep_online_interval=240,
        now=lambda: current,
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop_after_sleep(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop_after_sleep)
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    assert sleeps == [300]


@pytest.mark.parametrize(
    "failure",
    [UnsupportedCapability("forbidden"), ProtocolError("bad acknowledgement")],
)
async def test_keep_online_permanent_failure_stops_only_keeper_and_creates_repair(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    hass = Hass()
    create_issue = Mock()
    monkeypatch.setattr(
        "custom_components.time_messenger.runtime.ir.async_create_issue", create_issue
    )
    runtime = TimeMessengerRuntime(
        hass,
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        keep_online=AsyncMock(side_effect=failure),
        keep_online_schedule=workday_schedule(),
        keep_online_interval=240,
        now=lambda: MONDAY_MORNING,
    )  # type: ignore[arg-type]
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    assert runtime._generation == 1
    hass.config_entries.async_schedule_reload.assert_not_called()
    create_issue.assert_called_once_with(
        hass,
        "time_messenger",
        "keep_online_unavailable_entry",
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="keep_online_unavailable",
    )


async def test_keep_online_auth_failure_uses_standard_reauth_path() -> None:
    hass = Hass()
    entry = SimpleNamespace(
        entry_id="entry",
        async_get_active_flows=Mock(return_value=iter(())),
    )
    websocket = BlockingWebSocket()
    runtime = TimeMessengerRuntime(
        hass,
        entry,
        websocket,
        AsyncMock(),
        keep_online=AsyncMock(side_effect=AuthError("expired")),
        keep_online_schedule=workday_schedule(),
        keep_online_interval=240,
        now=lambda: MONDAY_MORNING,
    )  # type: ignore[arg-type]
    runtime._generation = 1

    await runtime._async_keep_online_loop(1)

    assert websocket.closed is True
    hass.config_entries.async_schedule_reload.assert_called_once_with("entry")


async def test_unload_during_auth_socket_close_suppresses_late_reload() -> None:
    class YieldingCloseWebSocket(BlockingWebSocket):
        def __init__(self) -> None:
            super().__init__()
            self.close_started = asyncio.Event()
            self.release_close = asyncio.Event()
            self.close_calls = 0

        async def async_close(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                self.close_started.set()
                await self.release_close.wait()
            self.closed = True

    hass = Hass()
    entry = SimpleNamespace(entry_id="entry")
    websocket = YieldingCloseWebSocket()
    runtime = TimeMessengerRuntime(hass, entry, websocket, AsyncMock())  # type: ignore[arg-type]
    runtime._generation = 1
    reload_task = asyncio.create_task(runtime._async_surface_auth_failure(1))
    await asyncio.wait_for(websocket.close_started.wait(), timeout=1)

    await runtime.async_stop()
    websocket.release_close.set()
    await asyncio.wait_for(reload_task, timeout=1)

    hass.config_entries.async_schedule_reload.assert_not_called()


async def test_unsupported_capability_creates_repair_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = SimpleNamespace(entry_id="entry")
    websocket = FailingWebSocket(UnsupportedCapability("disabled"))
    create_issue = Mock()
    monkeypatch.setattr(
        "custom_components.time_messenger.runtime.ir.async_create_issue", create_issue
    )
    runtime = TimeMessengerRuntime(Hass(), entry, websocket, AsyncMock())  # type: ignore[arg-type]
    runtime._generation = 1
    await runtime._async_supervise(1)
    create_issue.assert_called_once()
    assert websocket.calls == 1


@pytest.mark.parametrize(
    ("error", "expected_minimum"),
    [(TransientError("offline"), 1.0), (RateLimitError(30.0), 30.0)],
)
async def test_retry_uses_bounded_jitter_and_respects_rate_limit(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected_minimum: float
) -> None:
    entry = SimpleNamespace(entry_id="entry")
    websocket = FailingWebSocket(error)
    runtime = TimeMessengerRuntime(
        Hass(),
        entry,
        websocket,
        AsyncMock(),
        random_uniform=lambda low, high: high,  # type: ignore[arg-type]
    )
    sleeps: list[float] = []

    async def stop_after_delay(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop_after_delay)
    runtime._generation = 1
    await runtime._async_supervise(1)
    assert sleeps == [expected_minimum]
    assert 0 <= sleeps[0] <= max(60.0, expected_minimum)


async def test_zero_jitter_still_waits_at_least_one_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        FailingWebSocket(TransientError("offline")),
        AsyncMock(),
        random_uniform=lambda _low, _high: 0.0,
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop)
    runtime._generation = 1
    await runtime._async_supervise(1)
    assert sleeps == [1.0]


@pytest.mark.parametrize("delay", [float("nan"), float("inf"), 1000000.0])
async def test_rate_limit_delay_remains_finite_and_bounded(
    monkeypatch: pytest.MonkeyPatch, delay: float
) -> None:
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        FailingWebSocket(RateLimitError(delay)),
        AsyncMock(),
        random_uniform=lambda _low, _high: 0.0,
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop(value: float) -> None:
        sleeps.append(value)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop)
    runtime._generation = 1
    await runtime._async_supervise(1)
    assert len(sleeps) == 1
    assert 1.0 <= sleeps[0] <= 300.0


async def test_unexpected_listener_exception_retries_instead_of_killing_supervisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = FailingWebSocket(RuntimeError("payload must not escape"))
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        websocket,
        AsyncMock(),
        random_uniform=lambda _low, _high: 0.0,
    )  # type: ignore[arg-type]
    sleeps: list[float] = []

    async def stop(delay: float) -> None:
        sleeps.append(delay)
        runtime._generation += 1

    monkeypatch.setattr("custom_components.time_messenger.runtime.asyncio.sleep", stop)
    runtime._generation = 1
    await runtime._async_supervise(1)
    assert websocket.calls == 1
    assert sleeps == [1.0]


async def test_generation_guard_blocks_late_callback() -> None:
    pipeline = AsyncMock()
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        pipeline,
    )  # type: ignore[arg-type]
    runtime._generation = 2
    await runtime._async_process(AsyncMock(), 1)
    pipeline.async_process.assert_not_awaited()


async def test_unload_detaches_owned_ha_session_without_closing_it() -> None:
    session = SimpleNamespace(closed=False, detach=Mock(), close=AsyncMock())
    runtime = TimeMessengerRuntime(
        Hass(),
        SimpleNamespace(entry_id="entry"),
        BlockingWebSocket(),
        AsyncMock(),
        owned_session=session,
    )  # type: ignore[arg-type]
    await runtime.async_unload()
    session.detach.assert_called_once()
    session.close.assert_not_called()
