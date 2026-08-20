"""Strictly allowlisted diagnostics for Time Messenger."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_AUTH_MODE,
    CONF_INCLUDE_MESSAGE_TEXT,
    CONF_KEEP_ONLINE,
    CONF_KEEP_ONLINE_END_TIME,
    CONF_KEEP_ONLINE_INTERVAL_MINUTES,
    CONF_KEEP_ONLINE_START_TIME,
    CONF_KEEP_ONLINE_WEEKDAYS,
    CONF_SERVER_VERSION,
    CONF_TENANT_ORIGIN,
    CONF_USER_ID,
    DEFAULT_KEEP_ONLINE,
    DEFAULT_KEEP_ONLINE_END_TIME,
    DEFAULT_KEEP_ONLINE_INTERVAL_MINUTES,
    DEFAULT_KEEP_ONLINE_START_TIME,
    DEFAULT_KEEP_ONLINE_WEEKDAYS,
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
        "keep_online_enabled": entry.options.get(CONF_KEEP_ONLINE, DEFAULT_KEEP_ONLINE),
        "keep_online_weekdays": entry.options.get(
            CONF_KEEP_ONLINE_WEEKDAYS, DEFAULT_KEEP_ONLINE_WEEKDAYS
        ),
        "keep_online_start_time": entry.options.get(
            CONF_KEEP_ONLINE_START_TIME, DEFAULT_KEEP_ONLINE_START_TIME
        ),
        "keep_online_end_time": entry.options.get(
            CONF_KEEP_ONLINE_END_TIME, DEFAULT_KEEP_ONLINE_END_TIME
        ),
        "keep_online_interval_minutes": entry.options.get(
            CONF_KEEP_ONLINE_INTERVAL_MINUTES,
            DEFAULT_KEEP_ONLINE_INTERVAL_MINUTES,
        ),
        "listener_running": bool(
            entry.runtime_data.task is not None and not entry.runtime_data.task.done()
        )
        if entry.runtime_data is not None
        else False,
        "auth_health_running": bool(
            (health_task := getattr(entry.runtime_data, "health_task", None)) is not None
            and not health_task.done()
        )
        if entry.runtime_data is not None
        else False,
        "keep_online_running": bool(
            (keep_online_task := getattr(entry.runtime_data, "keep_online_task", None)) is not None
            and not keep_online_task.done()
        )
        if entry.runtime_data is not None
        else False,
    }
