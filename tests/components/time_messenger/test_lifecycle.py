"""Tests for unload/removal separation and local cleanup guarantees."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import RequestInfo
from homeassistant.const import Platform
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from custom_components.time_messenger import (
    _async_token_provider,
    _keep_online_settings,
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
from custom_components.time_messenger.const import (
    AUTH_MODE_OAUTH,
    CONF_AUTH_MODE,
    CONF_KEEP_ONLINE,
    CONF_KEEP_ONLINE_END_TIME,
    CONF_KEEP_ONLINE_INTERVAL_MINUTES,
    CONF_KEEP_ONLINE_START_TIME,
    CONF_KEEP_ONLINE_WEEKDAYS,
    DOMAIN,
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
        add_update_listener=Mock(),
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
        patch(
            "custom_components.time_messenger.TimeMessengerRuntime", return_value=runtime
        ) as runtime_factory,
        patch("custom_components.time_messenger.ir.async_delete_issue", delete_issue),
    ):
        assert await async_setup_entry(hass, entry) is True  # type: ignore[arg-type]
    client.async_get_me.assert_awaited_once()
    websocket.async_probe_hello.assert_awaited_once()
    runtime.async_start.assert_awaited_once()
    assert calls == ["forward_event", "runtime_start"]
    assert entry.runtime_data is runtime
    entry.add_update_listener.assert_not_called()
    health_check = runtime_factory.call_args.kwargs["health_check"]
    assert callable(health_check)
    client.async_get_me.return_value = {"id": "other-user"}
    with pytest.raises(AuthError, match="identity changed"):
        await health_check()
    assert runtime_factory.call_args.kwargs["keep_online"] is None
    assert runtime_factory.call_args.kwargs["keep_online_schedule"] is None
    assert runtime_factory.call_args.kwargs["keep_online_interval"] is None
    assert delete_issue.call_args_list == [
        ((hass, "time_messenger", "unsupported_tenant_entry"), {}),
        ((hass, "time_messenger", "keep_online_unavailable_entry"), {}),
    ]


def test_keep_online_settings_are_opt_in_and_fail_closed() -> None:
    assert _keep_online_settings({}) is None
    schedule, interval = _keep_online_settings({CONF_KEEP_ONLINE: True})  # type: ignore[misc]
    assert schedule.weekdays == frozenset({"mon", "tue", "wed", "thu", "fri"})
    assert schedule.start.isoformat() == "09:00:00"
    assert schedule.end.isoformat() == "18:00:00"
    assert interval == 4 * 60

    with pytest.raises(ValueError):
        _keep_online_settings(
            {
                CONF_KEEP_ONLINE: True,
                CONF_KEEP_ONLINE_WEEKDAYS: [],
            }
        )
    with pytest.raises(ValueError):
        _keep_online_settings(
            {
                CONF_KEEP_ONLINE: True,
                CONF_KEEP_ONLINE_INTERVAL_MINUTES: float("nan"),
            }
        )
    with pytest.raises(ValueError):
        _keep_online_settings(
            {
                CONF_KEEP_ONLINE: True,
                CONF_KEEP_ONLINE_INTERVAL_MINUTES: 4.5,
            }
        )


async def test_setup_wires_enabled_weekly_online_keeper() -> None:
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()))
    session = SimpleNamespace(detach=Mock(), close=AsyncMock())
    client = SimpleNamespace(
        async_get_me=AsyncMock(return_value={"id": "me"}),
        async_get_channel_type=AsyncMock(return_value="D"),
        async_set_online=AsyncMock(),
    )
    websocket = SimpleNamespace(async_probe_hello=AsyncMock(return_value="10.2"))
    runtime = SimpleNamespace(async_start=AsyncMock())
    entry = SimpleNamespace(
        entry_id="entry",
        data={
            "auth_mode": "pat",
            "tenant_origin": "https://time.example",
            "token": "secret",
            "user_id": "me",
        },
        options={
            CONF_KEEP_ONLINE: True,
            CONF_KEEP_ONLINE_WEEKDAYS: ["mon", "wed", "fri"],
            CONF_KEEP_ONLINE_START_TIME: "08:30:00",
            CONF_KEEP_ONLINE_END_TIME: "17:45:00",
            CONF_KEEP_ONLINE_INTERVAL_MINUTES: 3,
        },
        runtime_data=None,
    )
    with (
        patch(
            "custom_components.time_messenger._async_token_provider",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch("custom_components.time_messenger.create_time_session", return_value=session),
        patch("custom_components.time_messenger.TimeApiClient", return_value=client),
        patch("custom_components.time_messenger.TimeWebSocketClient", return_value=websocket),
        patch("custom_components.time_messenger.create_dedupe", return_value=SimpleNamespace()),
        patch(
            "custom_components.time_messenger.TimeMessengerRuntime", return_value=runtime
        ) as runtime_factory,
        patch("custom_components.time_messenger.ir.async_delete_issue") as delete_issue,
    ):
        assert await async_setup_entry(hass, entry) is True  # type: ignore[arg-type]

    kwargs = runtime_factory.call_args.kwargs
    assert kwargs["keep_online_schedule"].weekdays == frozenset({"mon", "wed", "fri"})
    assert kwargs["keep_online_schedule"].start.isoformat() == "08:30:00"
    assert kwargs["keep_online_schedule"].end.isoformat() == "17:45:00"
    assert kwargs["keep_online_interval"] == 180.0
    entry.data["user_id"] = "mutated-after-setup"
    await kwargs["keep_online"]()
    client.async_set_online.assert_awaited_once()
    args, online_kwargs = client.async_set_online.await_args
    assert args == ("me",)
    request_guard = online_kwargs["request_guard"]
    with patch(
        "custom_components.time_messenger.dt_util.now",
        return_value=datetime.fromisoformat("2026-08-19T12:00:00+03:00"),
    ):
        assert request_guard() is True
    with patch(
        "custom_components.time_messenger.dt_util.now",
        return_value=datetime.fromisoformat("2026-08-19T18:00:00+03:00"),
    ):
        assert request_guard() is False
    delete_issue.assert_called_once_with(hass, DOMAIN, "unsupported_tenant_entry")


def _oauth_request_error(
    error_type: type[OAuth2TokenRequestError], status: int
) -> OAuth2TokenRequestError:
    headers = CIMultiDictProxy(CIMultiDict())
    return error_type(
        request_info=RequestInfo(
            URL("https://time.example/oauth/access_token"),
            "POST",
            headers,
            URL("https://time.example/oauth/access_token"),
        ),
        history=(),
        status=status,
        message="redacted",
        headers=headers,
        domain=DOMAIN,
    )


@pytest.mark.parametrize(
    ("error_type", "status", "expected"),
    [
        (OAuth2TokenRequestReauthError, 400, AuthError),
        (OAuth2TokenRequestError, 400, TransientError),
        (OAuth2TokenRequestTransientError, 503, TransientError),
    ],
)
async def test_oauth_refresh_failures_are_classified_for_runtime(
    error_type: type[OAuth2TokenRequestError],
    status: int,
    expected: type[Exception],
) -> None:
    oauth_session = SimpleNamespace(
        async_ensure_token_valid=AsyncMock(side_effect=_oauth_request_error(error_type, status)),
        token={"access_token": "secret", "token_type": "bearer"},
    )
    entry = SimpleNamespace(data={CONF_AUTH_MODE: AUTH_MODE_OAUTH})
    with (
        patch(
            "custom_components.time_messenger.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch(
            "custom_components.time_messenger.config_entry_oauth2_flow.OAuth2Session",
            return_value=oauth_session,
        ),
    ):
        provider = await _async_token_provider(SimpleNamespace(), entry)  # type: ignore[arg-type]

    with pytest.raises(expected):
        await provider.async_get_token()


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
    delete_issue = Mock()
    with (
        patch("custom_components.time_messenger.create_time_session", return_value=session),
        patch("custom_components.time_messenger.TimeApiClient", return_value=client),
        patch("custom_components.time_messenger.async_remove_dedupe", purge),
        patch("custom_components.time_messenger.ir.async_delete_issue", delete_issue),
    ):
        await async_remove_entry(hass, entry)  # type: ignore[arg-type]
    client.async_logout.assert_awaited_once()
    session.detach.assert_called_once()
    session.close.assert_not_called()
    purge.assert_awaited_once_with(hass, "entry")
    assert delete_issue.call_args_list == [
        ((hass, DOMAIN, "unsupported_tenant_entry"), {}),
        ((hass, DOMAIN, "keep_online_unavailable_entry"), {}),
    ]
