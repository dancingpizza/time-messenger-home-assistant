"""Native config, reauth, and privacy options flows."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api.auth import StaticTokenProvider, token_from_oauth_data
from .api.client import TimeApiClient, normalize_tenant_origin
from .api.exceptions import AuthError, ProtocolError, TransientError, UnsupportedCapability
from .api.websocket import TimeWebSocketClient, create_time_session, release_time_session
from .const import (
    AUTH_MODE_OAUTH,
    AUTH_MODE_PAT,
    AUTH_MODE_SESSION,
    AUTH_MODES,
    CONF_AUTH_MODE,
    CONF_INCLUDE_MESSAGE_TEXT,
    CONF_SERVER_VERSION,
    CONF_TENANT_ORIGIN,
    CONF_USER_ID,
    DOMAIN,
)

CONF_MFA_CODE = "mfa_code"

# English fallback labels for the auth mode select. The frontend prefers the
# translated `selector.auth_mode.options.*` string and only falls back to
# these when a translation is missing.
_AUTH_MODE_LABELS: dict[str, str] = {
    AUTH_MODE_OAUTH: "OAuth",
    AUTH_MODE_PAT: "Personal access token",
    AUTH_MODE_SESSION: "Login and password",
}


class TimeMessengerConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Configure exactly one tenant origin and personal Time identity."""

    VERSION = 1

    def __init__(self) -> None:
        self._mode: str | None = None
        self._origin: str | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @property
    def logger(self) -> Any:
        import logging

        return logging.getLogger(__name__)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._origin = normalize_tenant_origin(user_input[CONF_TENANT_ORIGIN])
            except ValueError:
                errors[CONF_TENANT_ORIGIN] = "invalid_origin"
            else:
                self._mode = user_input[CONF_AUTH_MODE]
                next_step = await self._async_next_auth_step()
                if next_step is not None:
                    return next_step
                # OAuth was picked but no application credentials are
                # registered for this origin yet. Re-show this step instead
                # of aborting so the origin and mode the user just entered
                # are not lost; they can add credentials or pick another
                # auth mode without retyping the origin.
                errors["base"] = "oauth_not_configured"
        return self.async_show_form(
            step_id="user", data_schema=self._user_data_schema(), errors=errors
        )

    def _user_data_schema(self) -> vol.Schema:
        """Build the tenant/auth-mode schema, keeping any prior input as default."""

        origin_marker = (
            vol.Required(CONF_TENANT_ORIGIN, default=self._origin)
            if self._origin is not None
            else vol.Required(CONF_TENANT_ORIGIN)
        )
        mode_marker = (
            vol.Required(CONF_AUTH_MODE, default=self._mode)
            if self._mode is not None
            else vol.Required(CONF_AUTH_MODE)
        )
        return vol.Schema(
            {
                origin_marker: TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL, autocomplete="url")
                ),
                mode_marker: SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=mode, label=_AUTH_MODE_LABELS[mode])
                            for mode in AUTH_MODES
                        ],
                        translation_key=CONF_AUTH_MODE,
                    )
                ),
            }
        )

    async def _async_next_auth_step(self) -> Any:
        if self._mode == AUTH_MODE_PAT:
            return await self.async_step_pat()
        if self._mode == AUTH_MODE_SESSION:
            return await self.async_step_session()
        if self._mode == AUTH_MODE_OAUTH:
            assert self._origin is not None
            implementations = await config_entry_oauth2_flow.async_get_implementations(
                self.hass, DOMAIN
            )
            implementation = implementations.get(self._origin)
            if implementation is None:
                # Reauth has no form of its own to fall back to (mode and
                # origin come from the existing entry, not user input), so
                # it aborts. A fresh flow returns None and lets
                # async_step_user re-show itself with an inline error.
                if self._reauth_entry is not None:
                    return self.async_abort(reason="oauth_not_configured")
                return None
            self.flow_impl = implementation
            return await self.async_step_auth()
        return self.async_abort(reason="unsupported_auth_mode")

    async def async_step_pat(self, user_input: dict[str, Any] | None = None) -> Any:
        assert self._origin is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN]
            result = await self._async_validate(StaticTokenProvider(token))
            if isinstance(result, str):
                errors["base"] = result
            else:
                user_id, server_version = result
                return await self._async_finish(
                    user_id,
                    {CONF_TOKEN: token, CONF_SERVER_VERSION: server_version},
                )
        return self.async_show_form(
            step_id="pat",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
            description_placeholders={"tenant_origin": self._origin},
        )

    async def async_step_session(self, user_input: dict[str, Any] | None = None) -> Any:
        assert self._origin is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            login_client = TimeApiClient(session, self._origin, None)
            token: str | None = None
            committed = False
            try:
                token, login_user_id = await login_client.async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input.get(CONF_MFA_CODE),
                )
                result = await self._async_validate(StaticTokenProvider(token))
                if isinstance(result, str):
                    errors["base"] = result
                else:
                    user_id, server_version = result
                    if user_id != login_user_id:
                        errors["base"] = "identity_mismatch"
                    else:
                        flow_result = await self._async_finish(
                            user_id,
                            {CONF_TOKEN: token, CONF_SERVER_VERSION: server_version},
                        )
                        committed = flow_result.get("type") == FlowResultType.CREATE_ENTRY or (
                            flow_result.get("type") == FlowResultType.ABORT
                            and flow_result.get("reason") == "reauth_successful"
                        )
                        return flow_result
            except AuthError:
                errors["base"] = "invalid_auth"
            except UnsupportedCapability:
                errors["base"] = "unsupported"
            except ProtocolError, TransientError:
                errors["base"] = "cannot_connect"
            finally:
                if token is not None and not committed:
                    await self._async_logout_session(token)
        return self.async_show_form(
            step_id="session",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(autocomplete="username")
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD, autocomplete="current-password"
                        )
                    ),
                    vol.Optional(CONF_MFA_CODE): TextSelector(
                        TextSelectorConfig(autocomplete="one-time-code")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"tenant_origin": self._origin},
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> Any:
        """Validate OAuth identity and create/update the bound entry."""

        self._mode = AUTH_MODE_OAUTH
        if self._origin is None:
            auth_domain = self.context.get("auth_domain")
            if not isinstance(auth_domain, str):
                return self.async_abort(reason="invalid_origin")
            self._origin = normalize_tenant_origin(auth_domain)
        token = token_from_oauth_data(data["token"])
        result = await self._async_validate(StaticTokenProvider(token))
        if isinstance(result, str):
            return self.async_abort(reason=result)
        user_id, server_version = result
        return await self._async_finish(
            user_id,
            {
                "auth_implementation": data["auth_implementation"],
                "token": data["token"],
                CONF_SERVER_VERSION: server_version,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> Any:
        self._reauth_entry = self._get_reauth_entry()
        self._mode = entry_data[CONF_AUTH_MODE]
        self._origin = entry_data[CONF_TENANT_ORIGIN]
        return await self._async_next_auth_step()

    async def _async_validate(self, provider: StaticTokenProvider) -> tuple[str, str | None] | str:
        assert self._origin is not None
        session = create_time_session(self.hass)
        try:
            client = TimeApiClient(session, self._origin, provider)
            me = await client.async_get_me()
            websocket = TimeWebSocketClient(session, self._origin, provider)
            server_version = await websocket.async_probe_hello()
            return str(me["id"]), server_version
        except AuthError:
            return "invalid_auth"
        except UnsupportedCapability:
            return "unsupported"
        except ProtocolError, TransientError, ValueError:
            return "cannot_connect"
        finally:
            release_time_session(session)

    async def _async_logout_session(self, token: str) -> None:
        assert self._origin is not None
        try:
            client = TimeApiClient(
                async_get_clientsession(self.hass),
                self._origin,
                StaticTokenProvider(token),
            )
            await client.async_logout()
        except AuthError, ProtocolError, TransientError, UnsupportedCapability:
            pass

    async def _async_finish(
        self,
        user_id: str,
        auth_data: dict[str, Any],
    ) -> Any:
        assert self._mode is not None and self._origin is not None
        unique_id = f"{self._origin}|{user_id}"
        await self.async_set_unique_id(unique_id)
        data = {
            CONF_AUTH_MODE: self._mode,
            CONF_TENANT_ORIGIN: self._origin,
            CONF_USER_ID: user_id,
            **auth_data,
        }
        if self._reauth_entry is not None:
            if self._reauth_entry.unique_id != unique_id:
                return self.async_abort(reason="identity_mismatch")
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data_updates=data,
                reason="reauth_successful",
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=self._origin, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TimeMessengerOptionsFlow:
        return TimeMessengerOptionsFlow(config_entry)


class TimeMessengerOptionsFlow(config_entries.OptionsFlow):
    """Privacy-only options; origin and identity are immutable here."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INCLUDE_MESSAGE_TEXT,
                        default=self._entry.options.get(CONF_INCLUDE_MESSAGE_TEXT, False),
                    ): bool
                }
            ),
        )
