"""Tests for the single supervised listener and lifecycle."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.time_messenger.api.exceptions import (
    AuthError,
    RateLimitError,
    TransientError,
    UnsupportedCapability,
)
from custom_components.time_messenger.runtime import TimeMessengerRuntime


class Hass:
    def async_create_task(self, coroutine: object, _name: str) -> asyncio.Task[None]:
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
    entry = SimpleNamespace(entry_id="entry", async_start_reauth=AsyncMock())
    runtime = TimeMessengerRuntime(Hass(), entry, websocket, AsyncMock())  # type: ignore[arg-type]
    await runtime.async_start()
    await runtime.async_start()
    await websocket.started.wait()
    assert websocket.calls == 1
    task = runtime.task
    assert task is not None
    await runtime.async_stop()
    assert runtime.task is None
    assert task.done()
    assert websocket.closed is True


class FailingWebSocket:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    async def async_listen(self, _callback: object, _guard: object) -> float:
        self.calls += 1
        raise self.error

    async def async_close(self) -> None:
        return None


async def test_terminal_auth_starts_same_entry_reauth_without_retry() -> None:
    entry = SimpleNamespace(entry_id="entry", async_start_reauth=AsyncMock())
    websocket = FailingWebSocket(AuthError("expired"))
    runtime = TimeMessengerRuntime(Hass(), entry, websocket, AsyncMock())  # type: ignore[arg-type]
    await runtime.async_start()
    assert runtime.task is not None
    await runtime.task
    entry.async_start_reauth.assert_awaited_once()
    assert websocket.calls == 1


async def test_unsupported_capability_creates_repair_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = SimpleNamespace(entry_id="entry", async_start_reauth=AsyncMock())
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
    entry = SimpleNamespace(entry_id="entry", async_start_reauth=AsyncMock())
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
