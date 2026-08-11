"""Strictly allowlisted diagnostics for Time Messenger."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_AUTH_MODE,
    CONF_INCLUDE_MESSAGE_TEXT,
    CONF_SERVER_VERSION,
    CONF_TENANT_ORIGIN,
    CONF_USER_ID,
)


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: Any,
) -> dict[str, Any]:
    """Return metadata only; never serialize credentials or message content."""

    return {
        "entry_id": entry.entry_id,
        "auth_mode": entry.data.get(CONF_AUTH_MODE),
        "tenant_origin": entry.data.get(CONF_TENANT_ORIGIN),
        "user_id": entry.data.get(CONF_USER_ID),
        "server_version": entry.data.get(CONF_SERVER_VERSION),
        "include_message_text": entry.options.get(CONF_INCLUDE_MESSAGE_TEXT, False),
        "listener_running": bool(
            entry.runtime_data.task is not None and not entry.runtime_data.task.done()
        )
        if entry.runtime_data is not None
        else False,
    }
