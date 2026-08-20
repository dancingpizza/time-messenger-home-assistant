"""Time Messenger integration lifecycle."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .api.auth import OAuthTokenProvider, StaticTokenProvider, token_from_oauth_data
from .api.client import TimeApiClient
from .api.exceptions import AuthError, ProtocolError, TransientError, UnsupportedCapability
from .api.websocket import TimeWebSocketClient, create_time_session, release_time_session
from .const import (
    AUTH_MODE_OAUTH,
    AUTH_MODE_SESSION,
    CONF_AUTH_MODE,
    CONF_INCLUDE_MESSAGE_TEXT,
    CONF_KEEP_ONLINE,
    CONF_KEEP_ONLINE_END_TIME,
    CONF_KEEP_ONLINE_INTERVAL_MINUTES,
    CONF_KEEP_ONLINE_START_TIME,
    CONF_KEEP_ONLINE_WEEKDAYS,
    CONF_TENANT_ORIGIN,
    CONF_TOKEN,
    CONF_USER_ID,
    DEFAULT_KEEP_ONLINE,
    DEFAULT_KEEP_ONLINE_END_TIME,
    DEFAULT_KEEP_ONLINE_INTERVAL_MINUTES,
    DEFAULT_KEEP_ONLINE_START_TIME,
    DEFAULT_KEEP_ONLINE_WEEKDAYS,
    DOMAIN,
    MAX_KEEP_ONLINE_INTERVAL_MINUTES,
    MIN_KEEP_ONLINE_INTERVAL_MINUTES,
    keep_online_issue_id,
)
from .dedupe import async_remove_dedupe, create_dedupe
from .event import HomeAssistantEventPublisher
from .pipeline import MessagePipeline
from .runtime import TimeMessengerRuntime
from .schedule import KeepOnlineSchedule

type TimeMessengerConfigEntry = ConfigEntry[TimeMessengerRuntime]

PLATFORMS: list[Platform] = [Platform.EVENT]


async def _async_token_provider(
    hass: HomeAssistant, entry: TimeMessengerConfigEntry
) -> StaticTokenProvider | OAuthTokenProvider:
    if entry.data[CONF_AUTH_MODE] != AUTH_MODE_OAUTH:
        return StaticTokenProvider(entry.data[CONF_TOKEN])
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    async def async_get_oauth_token() -> str:
        try:
            await oauth_session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise AuthError("OAuth token refresh failed") from err
        except OAuth2TokenRequestError as err:
            raise TransientError("OAuth token refresh temporarily failed") from err
        return token_from_oauth_data(oauth_session.token)

    return OAuthTokenProvider(async_get_oauth_token)


async def _async_validate_identity(client: TimeApiClient, expected_user_id: str) -> None:
    """Validate the bearer and keep the ConfigEntry bound to one identity."""

    me = await client.async_get_me()
    if me["id"] != expected_user_id:
        raise AuthError("Time identity changed")


def _keep_online_settings(
    options: Mapping[str, Any],
) -> tuple[KeepOnlineSchedule, float] | None:
    """Build validated runtime settings without broadening a stored schedule."""

    if options.get(CONF_KEEP_ONLINE, DEFAULT_KEEP_ONLINE) is not True:
        return None
    interval = options.get(
        CONF_KEEP_ONLINE_INTERVAL_MINUTES,
        DEFAULT_KEEP_ONLINE_INTERVAL_MINUTES,
    )
    if (
        isinstance(interval, bool)
        or not isinstance(interval, int | float)
        or not math.isfinite(interval)
        or not float(interval).is_integer()
        or not MIN_KEEP_ONLINE_INTERVAL_MINUTES <= interval <= MAX_KEEP_ONLINE_INTERVAL_MINUTES
    ):
        raise ValueError("invalid keep-online interval")
    schedule = KeepOnlineSchedule(
        options.get(CONF_KEEP_ONLINE_WEEKDAYS, DEFAULT_KEEP_ONLINE_WEEKDAYS),
        options.get(CONF_KEEP_ONLINE_START_TIME, DEFAULT_KEEP_ONLINE_START_TIME),
        options.get(CONF_KEEP_ONLINE_END_TIME, DEFAULT_KEEP_ONLINE_END_TIME),
    )
    return schedule, float(interval) * 60.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimeMessengerConfigEntry,
) -> bool:
    """Gate identity/capability, then start one listener."""

    session = None
    try:
        provider = await _async_token_provider(hass, entry)
        session = create_time_session(hass)
        origin = entry.data[CONF_TENANT_ORIGIN]
        bound_user_id = entry.data[CONF_USER_ID]
        client = TimeApiClient(session, origin, provider)
        websocket = TimeWebSocketClient(session, origin, provider)
        await _async_validate_identity(client, bound_user_id)
        await websocket.async_probe_hello()
    except AuthError as err:
        if session is not None:
            release_time_session(session)
        raise ConfigEntryAuthFailed("Time credentials rejected") from err
    except UnsupportedCapability as err:
        if session is not None:
            release_time_session(session)
        ir.async_create_issue(
            hass,
            "time_messenger",
            f"unsupported_tenant_{entry.entry_id}",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="unsupported_tenant",
        )
        raise ConfigEntryError("Time WebSocket capability unavailable") from err
    except TransientError as err:
        if session is not None:
            release_time_session(session)
        raise ConfigEntryNotReady("Time tenant validation failed") from err
    except (KeyError, ProtocolError, TypeError, ValueError) as err:
        if session is not None:
            release_time_session(session)
        raise ConfigEntryError("Time entry configuration is invalid") from err
    except Exception as err:
        if session is not None:
            release_time_session(session)
        raise ConfigEntryNotReady("Time integration initialization failed") from err

    publisher = HomeAssistantEventPublisher(
        hass,
        config_entry_id=entry.entry_id,
        account_user_id=bound_user_id,
        include_message_text=entry.options.get(CONF_INCLUDE_MESSAGE_TEXT, False),
    )
    pipeline = MessagePipeline(
        account_user_id=bound_user_id,
        resolve_channel_type=client.async_get_channel_type,
        dedupe=create_dedupe(hass, entry.entry_id),
        publish=publisher.async_publish,
    )
    keep_online_enabled = entry.options.get(CONF_KEEP_ONLINE, DEFAULT_KEEP_ONLINE) is True
    try:
        keep_online_settings = _keep_online_settings(entry.options)
    except TypeError, ValueError:
        # OptionsFlow prevents this during normal use. If storage was edited or
        # corrupted, fail closed: keep receiving messages without making status
        # calls on a schedule different from the one the user chose.
        keep_online_settings = None
        ir.async_create_issue(
            hass,
            DOMAIN,
            keep_online_issue_id(entry.entry_id),
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="keep_online_unavailable",
        )
    keep_online_schedule, keep_online_interval = (
        keep_online_settings if keep_online_settings is not None else (None, None)
    )

    async def async_keep_online() -> bool:
        """Recheck the local window after a potentially slow token refresh."""

        assert keep_online_schedule is not None
        return await client.async_set_online(
            bound_user_id,
            request_guard=lambda: keep_online_schedule.is_active(dt_util.now()),
        )

    runtime = TimeMessengerRuntime(
        hass,
        entry,
        websocket,
        pipeline,
        owned_session=session,
        health_check=lambda: _async_validate_identity(client, bound_user_id),
        keep_online=async_keep_online if keep_online_settings is not None else None,
        keep_online_schedule=keep_online_schedule,
        keep_online_interval=keep_online_interval,
    )
    entry.runtime_data = runtime
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await runtime.async_start()
    except Exception:
        await runtime.async_unload()
        raise
    ir.async_delete_issue(hass, "time_messenger", f"unsupported_tenant_{entry.entry_id}")
    if not keep_online_enabled:
        ir.async_delete_issue(hass, DOMAIN, keep_online_issue_id(entry.entry_id))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TimeMessengerConfigEntry,
) -> bool:
    """Invalidate generation, wait for task, and close only local runtime resources."""

    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_unload()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: TimeMessengerConfigEntry) -> None:
    """Best-effort session logout, then unconditionally purge local dedupe state."""

    try:
        if entry.data.get(CONF_AUTH_MODE) == AUTH_MODE_SESSION and entry.data.get(CONF_TOKEN):
            session = None
            try:
                session = create_time_session(hass)
                client = TimeApiClient(
                    session,
                    entry.data[CONF_TENANT_ORIGIN],
                    StaticTokenProvider(entry.data[CONF_TOKEN]),
                )
                await client.async_logout()
            except AuthError, ProtocolError, TransientError, UnsupportedCapability:
                pass
            finally:
                if session is not None:
                    release_time_session(session)
    finally:
        try:
            await async_remove_dedupe(hass, entry.entry_id)
        finally:
            ir.async_delete_issue(hass, DOMAIN, f"unsupported_tenant_{entry.entry_id}")
            ir.async_delete_issue(hass, DOMAIN, keep_online_issue_id(entry.entry_id))
