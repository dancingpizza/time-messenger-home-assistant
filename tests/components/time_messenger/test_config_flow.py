"""Tests for explicit auth mode routing, identity binding, reauth, and options."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    SelectSelector,
    TimeSelector,
)

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
    CONF_KEEP_ONLINE,
    CONF_KEEP_ONLINE_END_TIME,
    CONF_KEEP_ONLINE_INTERVAL_MINUTES,
    CONF_KEEP_ONLINE_START_TIME,
    CONF_KEEP_ONLINE_WEEKDAYS,
    CONF_TENANT_ORIGIN,
    DEFAULT_KEEP_ONLINE_END_TIME,
    DEFAULT_KEEP_ONLINE_INTERVAL_MINUTES,
    DEFAULT_KEEP_ONLINE_START_TIME,
    DEFAULT_KEEP_ONLINE_WEEKDAYS,
    MAX_KEEP_ONLINE_INTERVAL_MINUTES,
    MIN_KEEP_ONLINE_INTERVAL_MINUTES,
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


async def test_oauth_without_credentials_keeps_reauth_action_open() -> None:
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
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "oauth_credentials"
    assert result["errors"] is None
    assert result["data_schema"]({}) == {}


async def test_oauth_reauth_resumes_after_credentials_are_restored() -> None:
    flow = TimeMessengerConfigFlow()
    flow.hass = SimpleNamespace()  # type: ignore[assignment]
    flow._origin = "https://time.example"
    implementation = SimpleNamespace()
    with (
        patch(
            "custom_components.time_messenger.config_flow.config_entry_oauth2_flow.async_get_implementations",
            AsyncMock(return_value={"https://time.example": implementation}),
        ),
        patch.object(
            flow,
            "async_step_auth",
            AsyncMock(return_value={"type": FlowResultType.EXTERNAL_STEP}),
        ) as auth,
    ):
        result = await flow.async_step_oauth_credentials({})
    assert flow.flow_impl is implementation
    auth.assert_awaited_once()
    assert result == {"type": FlowResultType.EXTERNAL_STEP}


@pytest.mark.parametrize(
    ("mode", "step_id"),
    [(AUTH_MODE_PAT, "pat"), (AUTH_MODE_SESSION, "session")],
)
async def test_credential_reauth_modes_stay_open_for_user_input(mode: str, step_id: str) -> None:
    flow = TimeMessengerConfigFlow()
    flow._mode = mode
    flow._origin = "https://time.example"
    flow._reauth_entry = SimpleNamespace(entry_id="entry")  # type: ignore[assignment]

    result = await flow._async_next_auth_step()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == step_id


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


async def test_options_exposes_privacy_and_online_keeper_defaults() -> None:
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options={}))  # type: ignore[arg-type]
    result = await flow.async_step_init()
    assert result["type"].value == "form"
    schema = result["data_schema"]
    assert schema({}) == {
        CONF_INCLUDE_MESSAGE_TEXT: False,
        CONF_KEEP_ONLINE: False,
        CONF_KEEP_ONLINE_WEEKDAYS: list(DEFAULT_KEEP_ONLINE_WEEKDAYS),
        CONF_KEEP_ONLINE_START_TIME: DEFAULT_KEEP_ONLINE_START_TIME,
        CONF_KEEP_ONLINE_END_TIME: DEFAULT_KEEP_ONLINE_END_TIME,
        CONF_KEEP_ONLINE_INTERVAL_MINUTES: DEFAULT_KEEP_ONLINE_INTERVAL_MINUTES,
    }
    validators = {marker.schema: validator for marker, validator in schema.schema.items()}
    assert isinstance(validators[CONF_INCLUDE_MESSAGE_TEXT], BooleanSelector)
    assert isinstance(validators[CONF_KEEP_ONLINE], BooleanSelector)
    assert isinstance(validators[CONF_KEEP_ONLINE_WEEKDAYS], SelectSelector)
    assert validators[CONF_KEEP_ONLINE_WEEKDAYS].config["multiple"] is True
    assert isinstance(validators[CONF_KEEP_ONLINE_START_TIME], TimeSelector)
    assert isinstance(validators[CONF_KEEP_ONLINE_END_TIME], TimeSelector)
    assert isinstance(validators[CONF_KEEP_ONLINE_INTERVAL_MINUTES], NumberSelector)


async def test_options_preserves_existing_values_and_saves_all_fields() -> None:
    existing = {
        CONF_INCLUDE_MESSAGE_TEXT: True,
        CONF_KEEP_ONLINE: True,
        CONF_KEEP_ONLINE_WEEKDAYS: ["tue", "thu"],
        CONF_KEEP_ONLINE_START_TIME: "08:30:00",
        CONF_KEEP_ONLINE_END_TIME: "17:15:00",
        CONF_KEEP_ONLINE_INTERVAL_MINUTES: 7,
    }
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options=existing))  # type: ignore[arg-type]

    form = await flow.async_step_init()
    assert form["data_schema"]({}) == existing

    saved = await flow.async_step_init(existing)
    assert saved["type"] == FlowResultType.CREATE_ENTRY
    assert saved["data"] == existing


async def test_options_normalizes_times_and_allows_cross_midnight_schedule() -> None:
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options={}))  # type: ignore[arg-type]
    submitted = {
        CONF_INCLUDE_MESSAGE_TEXT: False,
        CONF_KEEP_ONLINE: True,
        CONF_KEEP_ONLINE_WEEKDAYS: ["fri"],
        CONF_KEEP_ONLINE_START_TIME: "22:00",
        CONF_KEEP_ONLINE_END_TIME: "06:00",
        CONF_KEEP_ONLINE_INTERVAL_MINUTES: 4,
    }

    result = await flow.async_step_init(submitted)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_KEEP_ONLINE_START_TIME] == "22:00:00"
    assert result["data"][CONF_KEEP_ONLINE_END_TIME] == "06:00:00"


@pytest.mark.parametrize(
    ("weekdays", "start_time", "end_time"),
    [([], "09:00:00", "18:00:00"), (["mon"], "09:00", "09:00:00")],
)
async def test_options_rejects_empty_weekdays_or_zero_length_window(
    weekdays: list[str], start_time: str, end_time: str
) -> None:
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options={}))  # type: ignore[arg-type]

    result = await flow.async_step_init(
        {
            CONF_INCLUDE_MESSAGE_TEXT: False,
            CONF_KEEP_ONLINE: True,
            CONF_KEEP_ONLINE_WEEKDAYS: weekdays,
            CONF_KEEP_ONLINE_START_TIME: start_time,
            CONF_KEEP_ONLINE_END_TIME: end_time,
            CONF_KEEP_ONLINE_INTERVAL_MINUTES: 4,
        }
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_schedule"}
    assert result["data_schema"]({})[CONF_KEEP_ONLINE_WEEKDAYS] == weekdays


@pytest.mark.parametrize(
    "interval",
    [MIN_KEEP_ONLINE_INTERVAL_MINUTES - 1, MAX_KEEP_ONLINE_INTERVAL_MINUTES + 1],
)
async def test_online_keeper_interval_schema_rejects_out_of_range_values(interval: int) -> None:
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options={}))  # type: ignore[arg-type]
    result = await flow.async_step_init()

    with pytest.raises(vol.Invalid):
        result["data_schema"](
            {
                CONF_INCLUDE_MESSAGE_TEXT: False,
                CONF_KEEP_ONLINE: True,
                CONF_KEEP_ONLINE_INTERVAL_MINUTES: interval,
            }
        )


async def test_online_keeper_rejects_fractional_interval() -> None:
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options={}))  # type: ignore[arg-type]
    result = await flow.async_step_init(
        {
            CONF_INCLUDE_MESSAGE_TEXT: False,
            CONF_KEEP_ONLINE: True,
            CONF_KEEP_ONLINE_WEEKDAYS: ["mon"],
            CONF_KEEP_ONLINE_START_TIME: "09:00:00",
            CONF_KEEP_ONLINE_END_TIME: "18:00:00",
            CONF_KEEP_ONLINE_INTERVAL_MINUTES: 4.5,
        }
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_interval"}


async def test_online_keeper_schedule_schema_rejects_unknown_day_and_invalid_time() -> None:
    flow = TimeMessengerOptionsFlow(SimpleNamespace(options={}))  # type: ignore[arg-type]
    schema = (await flow.async_step_init())["data_schema"]

    with pytest.raises(vol.Invalid):
        schema({CONF_KEEP_ONLINE_WEEKDAYS: ["holiday"]})
    with pytest.raises(vol.Invalid):
        schema({CONF_KEEP_ONLINE_START_TIME: "25:00:00"})


def test_options_flow_uses_home_assistant_reload_helper() -> None:
    assert issubclass(TimeMessengerOptionsFlow, config_entries.OptionsFlowWithReload)


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
