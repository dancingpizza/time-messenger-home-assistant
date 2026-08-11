"""Time Messenger integration lifecycle."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import issue_registry as ir

from .api.auth import OAuthTokenProvider, StaticTokenProvider, token_from_oauth_data
from .api.client import TimeApiClient
from .api.exceptions import AuthError, ProtocolError, TransientError, UnsupportedCapability
from .api.websocket import TimeWebSocketClient, create_time_session, release_time_session
from .const import (
    AUTH_MODE_OAUTH,
    AUTH_MODE_SESSION,
    CONF_AUTH_MODE,
    CONF_INCLUDE_MESSAGE_TEXT,
    CONF_TENANT_ORIGIN,
    CONF_TOKEN,
    CONF_USER_ID,
)
from .dedupe import async_remove_dedupe, create_dedupe
from .event import HomeAssistantEventPublisher
from .pipeline import MessagePipeline
from .runtime import TimeMessengerRuntime

type TimeMessengerConfigEntry = ConfigEntry[TimeMessengerRuntime]


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
        except OAuth2TokenRequestError as err:
            raise AuthError("OAuth token refresh failed") from err
        return token_from_oauth_data(oauth_session.token)

    return OAuthTokenProvider(async_get_oauth_token)


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
        client = TimeApiClient(session, origin, provider)
        websocket = TimeWebSocketClient(session, origin, provider)
        me = await client.async_get_me()
        if me["id"] != entry.data[CONF_USER_ID]:
            raise AuthError("Time identity changed")
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
        account_user_id=entry.data[CONF_USER_ID],
        include_message_text=entry.options.get(CONF_INCLUDE_MESSAGE_TEXT, False),
    )
    pipeline = MessagePipeline(
        account_user_id=entry.data[CONF_USER_ID],
        resolve_channel_type=client.async_get_channel_type,
        dedupe=create_dedupe(hass, entry.entry_id),
        publish=publisher.async_publish,
    )
    runtime = TimeMessengerRuntime(
        hass,
        entry,
        websocket,
        pipeline,
        owned_session=session,
    )
    entry.runtime_data = runtime
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await runtime.async_start()
    ir.async_delete_issue(hass, "time_messenger", f"unsupported_tenant_{entry.entry_id}")
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: TimeMessengerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    _hass: HomeAssistant,
    entry: TimeMessengerConfigEntry,
) -> bool:
    """Invalidate generation, wait for task, and close only local runtime resources."""

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
        await async_remove_dedupe(hass, entry.entry_id)
