"""Tests for the stable public event payload."""

from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.time_messenger import event as event_module
from custom_components.time_messenger.event import HomeAssistantEventPublisher, event_data
from custom_components.time_messenger.models import DirectMessage


def message() -> DirectMessage:
    return DirectMessage(
        post_id="p1",
        channel_id="c1",
        sender_user_id="u2",
        message="classified",
        created_at="2026-08-11T12:00:00Z",
        sender_username="alex",
        root_id="r1",
        file_ids=("f1",),
    )


def test_message_text_is_redacted_by_default() -> None:
    data = event_data(
        message(), config_entry_id="entry", account_user_id="me", include_message_text=False
    )
    assert data == {
        "schema_version": 1,
        "type": "direct_message",
        "config_entry_id": "entry",
        "account_user_id": "me",
        "post_id": "p1",
        "channel_id": "c1",
        "sender_user_id": "u2",
        "message_text": None,
        "text_redacted": True,
        "created_at": "2026-08-11T12:00:00Z",
        "sender_username": "alex",
        "root_id": "r1",
        "file_ids": ["f1"],
    }


def test_message_text_requires_opt_in() -> None:
    data = event_data(
        message(), config_entry_id="entry", account_user_id="me", include_message_text=True
    )
    assert data["message_text"] == "classified"
    assert data["text_redacted"] is False


async def test_publisher_fires_exact_public_event() -> None:
    fired: list[tuple[str, dict[str, object]]] = []

    class Bus:
        def async_fire(self, event: str, data: dict[str, object]) -> None:
            fired.append((event, data))

    class Hass:
        def __init__(self) -> None:
            self.bus = Bus()
            self.data: dict[str, object] = {}

        def verify_event_loop_thread(self, _action: str) -> None:
            pass

    hass = Hass()
    publisher = HomeAssistantEventPublisher(
        hass, config_entry_id="entry", account_user_id="me", include_message_text=False
    )
    await publisher.async_publish(message())
    assert fired[0][0] == "time_messenger_event"
    assert fired[0][1]["message_text"] is None


async def test_publisher_delivers_same_payload_to_native_event_subscriber() -> None:
    fired: list[tuple[str, dict[str, object]]] = []
    received: list[dict[str, object]] = []

    class Bus:
        def async_fire(self, event: str, data: dict[str, object]) -> None:
            fired.append((event, data))

    class Hass:
        def __init__(self) -> None:
            self.bus = Bus()
            self.data: dict[str, object] = {}

        def verify_event_loop_thread(self, _action: str) -> None:
            pass

    hass = Hass()

    @callback
    def capture(data: dict[str, object]) -> None:
        received.append(data)

    async_dispatcher_connect(hass, event_module.message_signal("entry"), capture)  # type: ignore[arg-type]
    publisher = HomeAssistantEventPublisher(
        hass, config_entry_id="entry", account_user_id="me", include_message_text=False
    )

    await publisher.async_publish(message())

    assert len(fired) == 1
    assert received == [fired[0][1]]


async def test_event_platform_exposes_account_event_entity_and_records_message() -> None:
    class Hass:
        def __init__(self) -> None:
            self.data: dict[str, object] = {"dispatcher": defaultdict(dict)}

        def verify_event_loop_thread(self, _action: str) -> None:
            pass

    hass = Hass()
    entry = SimpleNamespace(
        entry_id="entry",
        unique_id="https://time.example|me",
        title="https://time.example",
        data={"tenant_origin": "https://time.example", "user_id": "me"},
    )
    entities: list[object] = []

    await event_module.async_setup_entry(hass, entry, entities.extend)  # type: ignore[arg-type]

    assert len(entities) == 1
    entity = entities[0]
    assert isinstance(entity, event_module.TimeMessengerEventEntity)
    assert entity.unique_id == "https://time.example|me_direct_message"
    assert entity.translation_key == "direct_message"
    assert entity.event_types == ["direct_message"]
    assert entity.device_info["entry_type"] is DeviceEntryType.SERVICE
    assert entity.device_info["identifiers"] == {("time_messenger", "https://time.example|me")}

    entity.hass = hass  # type: ignore[assignment]
    entity.entity_id = "event.time_messenger_direct_message"
    entity.async_write_ha_state = Mock()
    await entity.async_added_to_hass()
    payload = event_data(
        message(), config_entry_id="entry", account_user_id="me", include_message_text=False
    )

    event_module.async_dispatcher_send(
        hass,
        event_module.message_signal("entry"),
        payload,  # type: ignore[arg-type]
    )

    assert entity.state is not None
    assert entity.state_attributes == {"event_type": "direct_message", **payload}
