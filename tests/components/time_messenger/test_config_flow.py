"""Tests for explicit auth mode routing, identity binding, reauth, and options."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.time_messenger.config_flow import (
    TimeMessengerConfigFlow,
    TimeMessengerOptionsFlow,
)
from custom_components.time_messenger.const import (
    AUTH_MODE_OAUTH,
    AUTH_MODE_PAT,
    AUTH_MODE_SESSION,
    CONF_AUTH_MODE,
    CONF_INCLUDE_MESSAGE_TEXT,
    CONF_TENANT_ORIGIN,
)


@pytest.mark.parametrize(
    ("mode", "method"),
    [
        (AUTH_MODE_PAT, "async_step_pat"),
        (AUTH_MODE_SESSION, "async_step_session"),
        (AUTH_MODE_OAUTH, "async_step_auth"),
    ],
)
async def test_three_auth_modes_are_explicit_and_never_fallback(mode: str, method: str) -> None:
    flow = TimeMessengerConfigFlow()
    flow._mode = mode
    flow._origin = "https://time.example"
    oauth_impl = SimpleNamespace()
    with (
        patch.object(flow, method, AsyncMock(return_value={"step": method})) as selected,
        patch(
            "custom_components.time_messenger.config_flow.config_entry_oauth2_flow.async_get_implementations",
            AsyncMock(return_value={"https://time.example": oauth_impl}),
        ),
    ):
        flow.hass = SimpleNamespace()  # type: ignore[assignment]
        result = await flow._async_next_auth_step()
    selected.assert_awaited_once()
    assert result == {"step": method}
    if mode == AUTH_MODE_OAUTH:
        assert flow.flow_impl is oauth_impl


async def test_oauth_without_credentials_reshows_user_form_with_error() -> None:
    flow = TimeMessengerConfigFlow()
    flow.hass = SimpleNamespace()  # type: ignore[assignment]
    with patch(
        "custom_components.time_messenger.config_flow.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(return_value={}),
    ):
        result = await flow.async_step_user(
            {CONF_TENANT_ORIGIN: "https://time.example", CONF_AUTH_MODE: AUTH_MODE_OAUTH}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "oauth_not_configured"}
    # The origin and mode the user just entered are kept, not discarded, so
    # the re-shown form can default to them instead of starting from blank.
    assert flow._origin == "https://time.example"
    assert flow._mode == AUTH_MODE_OAUTH
    assert result["data_schema"]({}) == {
        CONF_TENANT_ORIGIN: "https://time.example",
        CONF_AUTH_MODE: AUTH_MODE_OAUTH,
    }


async def test_oauth_without_credentials_aborts_during_reauth() -> None:
    flow = TimeMessengerConfigFlow()
    flow.hass = SimpleNamespace()  # type: ignore[assignment]
    flow._mode = AUTH_MODE_OAUTH
    flow._origin = "https://time.example"
    flow._reauth_entry = SimpleNamespace(entry_id="entry")  # type: ignore[assignment]
    with patch(
        "custom_components.time_messenger.config_flow.config_entry_oauth2_flow.async_get_implementations",
        AsyncMock(return_value={}),
    ):
        result = await flow._async_next_auth_step()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_not_configured"


async def test_reauth_uses_existing_mode_and_origin() -> None:
    flow = TimeMessengerConfigFlow()
    entry = SimpleNamespace(entry_id="entry")
    with (
        patch.object(flow, "_get_reauth_entry", return_value=entry),
        patch.object(flow, "_async_next_auth_step", AsyncMock(return_value={"type": "form"})),
    ):
        result = await flow.async_step_reauth(
            {CONF_AUTH_MODE: AUTH_MODE_PAT, CONF_TENANT_ORIGIN: "https://time.example"}
        )
    assert flow._reauth_entry is entry
    assert flow._mode == AUTH_MODE_PAT
    assert flow._origin == "https://time.example"
    assert result == {"type": "form"}


async def test_finish_binds_unique_id_to_origin_and_user() -> None:
    flow = TimeMessengerConfigFlow()
    flow._mode = AUTH_MODE_PAT
    flow._origin = "https://time.example"
    flow.async_set_unique_id = AsyncMock()  # type: ignore[method-assign]
    flow._abort_if_unique_id_configured = lambda: None  # type: ignore[method-assign]
    flow.async_create_entry = lambda **kwargs: kwargs  # type: ignore[method-assign]
    result = await flow._async_finish("user-1", {"token": "secret"})
    flow.async_set_unique_id.assert_awaited_once_with("https://time.example|user-1")
    assert result["data"]["user_id"] == "user-1"
    assert result["data"][CONF_AUTH_MODE] == AUTH_MODE_PAT


async def test_options_only_exposes_privacy_opt_in() -> None:
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options={}))  # type: ignore[arg-type]
    result = await flow.async_step_init()
    assert result["type"].value == "form"
    schema = result["data_schema"]
    assert schema({}) == {CONF_INCLUDE_MESSAGE_TEXT: False}


async def test_session_password_and_mfa_are_never_persisted() -> None:
    flow = TimeMessengerConfigFlow()
    flow.hass = SimpleNamespace()  # type: ignore[assignment]
    flow._mode = AUTH_MODE_SESSION
    flow._origin = "https://time.example"
    login = AsyncMock(return_value=("bearer", "user-1"))
    client = SimpleNamespace(async_login=login)
    finish = AsyncMock(return_value={"type": "create_entry"})
    with (
        patch(
            "custom_components.time_messenger.config_flow.async_get_clientsession",
            return_value=SimpleNamespace(),
        ),
        patch("custom_components.time_messenger.config_flow.TimeApiClient", return_value=client),
        patch.object(flow, "_async_validate", AsyncMock(return_value=("user-1", "10.2"))),
        patch.object(flow, "_async_finish", finish),
    ):
        await flow.async_step_session(
            {"username": "login", "password": "password", "mfa_code": "123456"}
        )
    login.assert_awaited_once_with("login", "password", "123456")
    persisted = finish.await_args.args[1]
    assert persisted == {"token": "bearer", "server_version": "10.2"}


@pytest.mark.parametrize(
    ("validation", "finish_result"),
    [
        ("cannot_connect", None),
        (("different-user", "10.2"), None),
        (
            ("user-1", "10.2"),
            {"type": FlowResultType.ABORT, "reason": "already_configured"},
        ),
    ],
)
async def test_session_token_is_logged_out_when_flow_does_not_commit(
    validation: str | tuple[str, str], finish_result: dict[str, object] | None
) -> None:
    flow = TimeMessengerConfigFlow()
    flow.hass = SimpleNamespace()  # type: ignore[assignment]
    flow._mode = AUTH_MODE_SESSION
    flow._origin = "https://time.example"
    login_client = SimpleNamespace(async_login=AsyncMock(return_value=("bearer", "user-1")))
    logout_client = SimpleNamespace(async_logout=AsyncMock())
    finish = AsyncMock(return_value=finish_result)
    with (
        patch(
            "custom_components.time_messenger.config_flow.async_get_clientsession",
            return_value=SimpleNamespace(),
        ),
        patch(
            "custom_components.time_messenger.config_flow.TimeApiClient",
            side_effect=[login_client, logout_client],
        ),
        patch.object(flow, "_async_validate", AsyncMock(return_value=validation)),
        patch.object(flow, "_async_finish", finish),
    ):
        await flow.async_step_session(
            {"username": "login", "password": "password", "mfa_code": "123456"}
        )
    logout_client.async_logout.assert_awaited_once()


async def test_validation_detaches_ha_created_session() -> None:
    flow = TimeMessengerConfigFlow()
    flow.hass = SimpleNamespace()  # type: ignore[assignment]
    flow._origin = "https://time.example"
    session = SimpleNamespace(detach=Mock(), close=AsyncMock())
    client = SimpleNamespace(async_get_me=AsyncMock(return_value={"id": "me"}))
    websocket = SimpleNamespace(async_probe_hello=AsyncMock(return_value="10.2"))
    with (
        patch(
            "custom_components.time_messenger.config_flow.create_time_session", return_value=session
        ),
        patch("custom_components.time_messenger.config_flow.TimeApiClient", return_value=client),
        patch(
            "custom_components.time_messenger.config_flow.TimeWebSocketClient",
            return_value=websocket,
        ),
    ):
        assert await flow._async_validate(SimpleNamespace()) == ("me", "10.2")  # type: ignore[arg-type]
    session.detach.assert_called_once()
    session.close.assert_not_called()
