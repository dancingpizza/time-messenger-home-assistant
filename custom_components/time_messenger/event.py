"""Home Assistant event schema adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_TENANT_ORIGIN,
    DOMAIN,
    EVENT_SCHEMA_VERSION,
    EVENT_TIME_MESSENGER,
    EVENT_TYPE_DIRECT_MESSAGE,
    message_signal,
)
from .models import DirectMessage
from .runtime import TimeMessengerRuntime

type TimeMessengerConfigEntry = ConfigEntry[TimeMessengerRuntime]


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TimeMessengerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the native message event for one Time account."""

    async_add_entities([TimeMessengerEventEntity(entry)])


class TimeMessengerEventEntity(EventEntity):
    """Represent accepted direct messages as native Home Assistant events."""

    _attr_has_entity_name = True
    _attr_suggested_object_id = "time_messenger_direct_message"
    _attr_translation_key = "direct_message"

    def __init__(self, entry: TimeMessengerConfigEntry) -> None:
        """Initialize an entry-scoped direct-message event entity."""

        assert entry.unique_id is not None
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.unique_id}_direct_message"
        self._attr_event_types = [EVENT_TYPE_DIRECT_MESSAGE]
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer="Time Messenger",
            model="Account",
            configuration_url=entry.data[CONF_TENANT_ORIGIN],
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to accepted messages for this config entry."""

        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                message_signal(self._entry_id),
                self._async_handle_message,
            )
        )

    @callback
    def _async_handle_message(self, data: dict[str, Any]) -> None:
        """Record one accepted direct message as an entity event."""

        self._trigger_event(EVENT_TYPE_DIRECT_MESSAGE, data)
        self.async_write_ha_state()


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
        hass: HomeAssistant,
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
        async_dispatcher_send(self._hass, message_signal(self._config_entry_id), data)


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
