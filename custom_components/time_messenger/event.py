"""Home Assistant event schema adapter."""

from collections.abc import Mapping
from typing import Any

from .const import EVENT_SCHEMA_VERSION, EVENT_TIME_MESSENGER
from .models import DirectMessage


def event_data(
    message: DirectMessage,
    *,
    config_entry_id: str,
    account_user_id: str,
    include_message_text: bool,
) -> dict[str, object]:
    """Build the stable, flat schema-v1 payload."""

    data: dict[str, object] = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "type": "direct_message",
        "config_entry_id": config_entry_id,
        "account_user_id": account_user_id,
        "post_id": message.post_id,
        "channel_id": message.channel_id,
        "sender_user_id": message.sender_user_id,
        "message_text": message.message if include_message_text else None,
        "text_redacted": not include_message_text,
        "created_at": message.created_at,
    }
    if message.sender_username is not None:
        data["sender_username"] = message.sender_username
    if message.root_id is not None:
        data["root_id"] = message.root_id
    if message.file_ids:
        data["file_ids"] = list(message.file_ids)
    return data


class HomeAssistantEventPublisher:
    """Publish the public event without retaining raw wire data."""

    def __init__(
        self,
        hass: Any,
        *,
        config_entry_id: str,
        account_user_id: str,
        include_message_text: bool,
    ) -> None:
        self._hass = hass
        self._config_entry_id = config_entry_id
        self._account_user_id = account_user_id
        self._include_message_text = include_message_text

    async def async_publish(self, message: DirectMessage) -> None:
        data = event_data(
            message,
            config_entry_id=self._config_entry_id,
            account_user_id=self._account_user_id,
            include_message_text=self._include_message_text,
        )
        self._hass.bus.async_fire(EVENT_TIME_MESSENGER, data)


def diagnostics_safe_event_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return only non-content event metadata for internal diagnostics."""

    allowed = {
        "schema_version",
        "type",
        "config_entry_id",
        "account_user_id",
        "post_id",
        "channel_id",
        "sender_user_id",
        "text_redacted",
        "created_at",
    }
    return {key: value for key, value in data.items() if key in allowed}
