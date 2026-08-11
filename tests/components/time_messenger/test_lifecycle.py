"""Tests for unload/removal separation and local cleanup guarantees."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady

from custom_components.time_messenger import (
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.time_messenger.api.exceptions import (
    AuthError,
    ProtocolError,
    TransientError,
    UnsupportedCapability,
)


async def test_unload_only_stops_runtime() -> None:
    calls: list[str] = []

    async def unload_platforms(_entry: object, platforms: list[Platform]) -> bool:
        assert platforms == [Platform.EVENT]
        calls.append("unload_event")
        return True

    async def unload_runtime() -> None:
        calls.append("runtime_unload")

    runtime = SimpleNamespace(async_unload=AsyncMock(side_effect=unload_runtime))
    entry = SimpleNamespace(runtime_data=runtime)
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_unload_platforms=unload_platforms))

    assert await async_unload_entry(hass, entry) is True  # type: ignore[arg-type]
    runtime.async_unload.assert_awaited_once()
    assert calls == ["unload_event", "runtime_unload"]


async def test_failed_platform_unload_keeps_runtime_active() -> None:
    runtime = SimpleNamespace(async_unload=AsyncMock())
    entry = SimpleNamespace(runtime_data=runtime)
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=False))
    )

    assert await async_unload_entry(hass, entry) is False  # type: ignore[arg-type]
    runtime.async_unload.assert_not_awaited()


async def test_setup_gates_identity_and_hello_before_starting_one_runtime() -> None:
    calls: list[str] = []

    async def forward_platforms(_entry: object, platforms: list[Platform]) -> None:
        assert platforms == [Platform.EVENT]
        calls.append("forward_event")

    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_forward_entry_setups=forward_platforms)
    )
    session = SimpleNamespace(detach=Mock(), close=AsyncMock())
    provider = SimpleNamespace()
    client = SimpleNamespace(
        async_get_me=AsyncMock(return_value={"id": "me"}),
        async_get_channel_type=AsyncMock(return_value="D"),
    )
    websocket = SimpleNamespace(async_probe_hello=AsyncMock(return_value="10.2"))

    async def start_runtime() -> None:
        calls.append("runtime_start")

    runtime = SimpleNamespace(async_start=AsyncMock(side_effect=start_runtime))
    entry = SimpleNamespace(
        entry_id="entry",
        data={
            "auth_mode": "pat",
            "tenant_origin": "https://time.example",
            "token": "secret",
            "user_id": "me",
        },
        options={},
        runtime_data=None,
        add_update_listener=lambda callback: callback,
        async_on_unload=lambda _callback: None,
    )
    delete_issue = Mock()
    with (
        patch(
            "custom_components.time_messenger._async_token_provider",
            AsyncMock(return_value=provider),
        ),
        patch("custom_components.time_messenger.create_time_session", return_value=session),
        patch("custom_components.time_messenger.TimeApiClient", return_value=client),
        patch("custom_components.time_messenger.TimeWebSocketClient", return_value=websocket),
        patch("custom_components.time_messenger.create_dedupe", return_value=SimpleNamespace()),
        patch("custom_components.time_messenger.TimeMessengerRuntime", return_value=runtime),
        patch("custom_components.time_messenger.ir.async_delete_issue", delete_issue),
    ):
        assert await async_setup_entry(hass, entry) is True  # type: ignore[arg-type]
    client.async_get_me.assert_awaited_once()
    websocket.async_probe_hello.assert_awaited_once()
    runtime.async_start.assert_awaited_once()
    assert calls == ["forward_event", "runtime_start"]
    assert entry.runtime_data is runtime
    delete_issue.assert_called_once_with(hass, "time_messenger", "unsupported_tenant_entry")


async def test_unsupported_setup_is_permanent_and_detaches_session() -> None:
    hass = SimpleNamespace()
    session = SimpleNamespace(detach=Mock(), close=AsyncMock())
    entry = SimpleNamespace(
        entry_id="entry",
        data={
            "auth_mode": "pat",
            "tenant_origin": "https://time.example",
            "token": "secret",
            "user_id": "me",
        },
    )
    client = SimpleNamespace(async_get_me=AsyncMock(side_effect=UnsupportedCapability("off")))
    create_issue = Mock()
    with (
        patch(
            "custom_components.time_messenger._async_token_provider",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch("custom_components.time_messenger.create_time_session", return_value=session),
        patch("custom_components.time_messenger.TimeApiClient", return_value=client),
        patch("custom_components.time_messenger.TimeWebSocketClient"),
        patch("custom_components.time_messenger.ir.async_create_issue", create_issue),
    ):
        with pytest.raises(ConfigEntryError):
            await async_setup_entry(hass, entry)  # type: ignore[arg-type]
    create_issue.assert_called_once()
    session.detach.assert_called_once()
    session.close.assert_not_called()


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (AuthError("expired"), ConfigEntryAuthFailed),
        (TransientError("offline"), ConfigEntryNotReady),
        (ProtocolError("bad config"), ConfigEntryError),
    ],
)
async def test_provider_initialization_failures_are_classified(
    failure: Exception, expected: type[Exception]
) -> None:
    create_session = Mock()
    with (
        patch(
            "custom_components.time_messenger._async_token_provider",
            AsyncMock(side_effect=failure),
        ),
        patch("custom_components.time_messenger.create_time_session", create_session),
    ):
        with pytest.raises(expected):
            await async_setup_entry(SimpleNamespace(), SimpleNamespace(entry_id="entry"))  # type: ignore[arg-type]
    create_session.assert_not_called()


async def test_client_initialization_failure_detaches_created_session() -> None:
    session = SimpleNamespace(detach=Mock(), close=AsyncMock())
    entry = SimpleNamespace(
        entry_id="entry",
        data={"auth_mode": "pat", "tenant_origin": "bad", "token": "secret"},
    )
    with (
        patch(
            "custom_components.time_messenger._async_token_provider",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch("custom_components.time_messenger.create_time_session", return_value=session),
        patch("custom_components.time_messenger.TimeApiClient", side_effect=ValueError("origin")),
    ):
        with pytest.raises(ConfigEntryError):
            await async_setup_entry(SimpleNamespace(), entry)  # type: ignore[arg-type]
    session.detach.assert_called_once()
    session.close.assert_not_called()


async def test_session_logout_failure_does_not_block_local_dedupe_purge() -> None:
    hass = SimpleNamespace()
    entry = SimpleNamespace(
        entry_id="entry",
        data={
            "auth_mode": "session",
            "tenant_origin": "https://time.example",
            "token": "secret",
        },
    )
    session = SimpleNamespace(detach=Mock(), close=AsyncMock())
    client = SimpleNamespace(async_logout=AsyncMock(side_effect=TransientError("remote down")))
    purge = AsyncMock()
    with (
        patch("custom_components.time_messenger.create_time_session", return_value=session),
        patch("custom_components.time_messenger.TimeApiClient", return_value=client),
        patch("custom_components.time_messenger.async_remove_dedupe", purge),
    ):
        await async_remove_entry(hass, entry)  # type: ignore[arg-type]
    client.async_logout.assert_awaited_once()
    session.detach.assert_called_once()
    session.close.assert_not_called()
    purge.assert_awaited_once_with(hass, "entry")
