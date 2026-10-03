"""Regression coverage for runtime tasks delaying Home Assistant startup."""

import asyncio
from pathlib import Path
from types import MappingProxyType
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.time_messenger.runtime import TimeMessengerRuntime
from custom_components.time_messenger.schedule import KeepOnlineSchedule


@pytest.mark.parametrize(
    ("health", "presence"), [(False, False), (True, False), (False, True), (True, True)]
)
async def test_live_runtime_does_not_block_ha_startup(
    tmp_path: Path, health: bool, presence: bool
) -> None:
    """HA can drain setup work while listener and optional loops stay alive."""
    hass = HomeAssistant(str(tmp_path))
    entry = ConfigEntry(
        domain="time_messenger",
        title="Test",
        data={},
        options={},
        source="user",
        version=1,
        minor_version=1,
        unique_id="test",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )
    listening = asyncio.Event()

    async def listen(*_args: object) -> float:
        listening.set()
        await asyncio.Event().wait()
        return 0

    websocket = AsyncMock()
    websocket.async_listen.side_effect = listen
    runtime = TimeMessengerRuntime(
        hass,
        entry,
        websocket,
        AsyncMock(),
        health_check=AsyncMock() if health else None,
        keep_online=AsyncMock(return_value=False) if presence else None,
        keep_online_schedule=KeepOnlineSchedule(
            ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "00:00:00", "23:59:59"
        )
        if presence
        else None,
        keep_online_interval=3600 if presence else None,
    )
    try:
        await runtime.async_start()
        await asyncio.wait_for(listening.wait(), timeout=1)
        await asyncio.wait_for(hass.async_block_till_done(), timeout=0.5)
        tasks = [runtime.task]
        if health:
            tasks.append(runtime.health_task)
        if presence:
            tasks.append(runtime.keep_online_task)
        assert all(task is not None and not task.done() for task in tasks)
        await runtime.async_unload()
        assert all(task is not None and task.cancelled() for task in tasks)
    finally:
        await runtime.async_unload()
        hass.import_executor.shutdown(wait=True)
