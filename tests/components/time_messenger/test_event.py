"""Tests for the stable public event payload."""

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

    hass = type("Hass", (), {"bus": Bus()})()
    publisher = HomeAssistantEventPublisher(
        hass, config_entry_id="entry", account_user_id="me", include_message_text=False
    )
    await publisher.async_publish(message())
    assert fired[0][0] == "time_messenger_event"
    assert fired[0][1]["message_text"] is None
