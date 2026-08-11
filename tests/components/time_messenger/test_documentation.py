"""Contract tests for the HACS README and neutral repository icon."""

import json
import re
import struct
import zlib
from pathlib import Path

import yaml

from custom_components.time_messenger.event import event_data
from custom_components.time_messenger.models import DirectMessage

REPOSITORY_ROOT = Path(__file__).parents[3]
README_PATH = REPOSITORY_ROOT / "README.md"
ICON_PATH = REPOSITORY_ROOT / "brand" / "icon.png"
HACS_MY_LINK = (
    "https://my.home-assistant.io/redirect/hacs_repository/"
    "?owner=dancingpizza&repository=time-messenger-home-assistant&category=integration"
)
ISSUES_URL = "https://github.com/dancingpizza/time-messenger-home-assistant/issues"


def readme() -> str:
    """Read the user-facing documentation."""
    return README_PATH.read_text(encoding="utf-8")


def heading_position(markdown: str, heading: str) -> int:
    """Return the exact H2 heading position."""
    match = re.search(rf"^## {re.escape(heading)}$", markdown, re.MULTILINE)
    assert match is not None, f"Missing README section: {heading}"
    return match.start()


def fenced_blocks(markdown: str, language: str) -> list[str]:
    """Extract fenced code blocks with the requested language."""
    return re.findall(rf"```{language}\n(.*?)\n```", markdown, re.DOTALL)


def test_readme_supports_a_safe_compatibility_decision() -> None:
    """Matrix: the cold reader can decide whether installation is appropriate."""
    markdown = readme()

    assert len(re.findall(r"^# ", markdown, re.MULTILINE)) == 1
    assert not re.search(r"^####+ ", markdown, re.MULTILINE)
    assert "неофициальная integration" in markdown.lower()
    assert "Home Assistant 2026.8.1+" in markdown
    assert "Time API v4" in markdown
    assert "acceptance probe" in markdown
    assert "1:1" in markdown and "`D`" in markdown
    for unsupported_scope in ("`G`", "`P`", "`O`", "backfill"):
        assert unsupported_scope in markdown
    assert "gap-free" in markdown
    assert "automation actions" in markdown
    assert all(teaser in markdown.lower() for teaser in ("notification", "свет", "tts"))
    ordered_sections = (
        "Установка",
        "Авторизация",
        "Privacy и event schema",
        "Пользовательские automation recipes",
        "Эксплуатация и troubleshooting",
        "Удаление и поддержка",
    )
    positions = [heading_position(markdown, heading) for heading in ordered_sections]
    assert positions == sorted(positions)


def test_readme_documents_hacs_and_manual_recovery() -> None:
    """Matrix: both installation paths are explicit and release-aware."""
    markdown = readme()

    assert HACS_MY_LINK in markdown
    assert "dancingpizza/time-messenger-home-assistant" in markdown
    assert "Settings > Devices & services" in markdown
    assert "перезапуст" in markdown.lower()
    assert "custom_components/time_messenger" in markdown
    assert "GitHub Release" in markdown
    assert "после push" in markdown
    assert "scripts/probe_time_tenant.py" in markdown
    assert "не заменяет полный acceptance probe" in markdown
    assert "Замените `https://time.example.org`" in markdown


def test_auth_choice_is_ordered_and_never_falls_back_automatically() -> None:
    """Matrix: readers choose an allowed mode and recover within that mode."""
    markdown = readme()
    auth = markdown[heading_position(markdown, "Авторизация") :]

    assert auth.index("### OAuth") < auth.index("### PAT") < auth.index("### Session")
    assert "рекоменду" in auth[auth.index("### OAuth") : auth.index("### PAT")].lower()
    assert "self-service" in auth[auth.index("### PAT") : auth.index("### Session")].lower()
    session = auth[auth.index("### Session") :]
    assert "fallback" in session
    assert "MFA" in session and "SSO" in session
    assert "browser" in session.lower()
    assert "автоматическ" in auth.lower() and "не переключ" in auth.lower()
    assert "том же mode" in auth.lower()
    assert "Не добавляйте path, `/api/v4`, query или fragment" in auth  # noqa: RUF001
    assert "меню с тремя точками > Application credentials" in auth  # noqa: RUF001
    assert "normalized tenant origin" in auth


def test_readme_contains_the_exact_redacted_schema_v1() -> None:
    """Matrix: privacy default and metadata fallback match the runtime event."""
    markdown = readme()
    json_blocks = fenced_blocks(markdown, "json")
    assert len(json_blocks) == 1

    payload = json.loads(json_blocks[0])
    expected = event_data(
        DirectMessage(
            post_id="post-example",
            channel_id="channel-example",
            sender_user_id="user-colleague",
            message="not included in the redacted event",
            created_at="2026-08-11T12:00:00Z",
            sender_username="colleague",
            root_id="root-example",
            file_ids=("file-example",),
        ),
        config_entry_id="01JEXAMPLEENTRY",
        account_user_id="user-current",
        include_message_text=False,
    )
    assert payload == expected
    assert "secrets" in markdown.lower() and "raw payload" in markdown.lower()
    assert "logs" in markdown.lower() and "diagnostics" in markdown.lower()
    assert "metadata тоже могут быть чувствительными" in markdown
    assert "Developer Tools > Events" in markdown
    assert "Код этой integration не добавляет secrets и raw payload" in markdown
    assert "UTC в формате ISO 8601" in markdown
    assert "`file_ids` отсутствует у сообщения без вложений" in markdown  # noqa: RUF001


def test_all_three_user_automation_recipes_are_parseable() -> None:
    """Matrix: notification, light and TTS recipes are safe to copy and adapt."""
    markdown = readme()
    recipes = fenced_blocks(markdown, "yaml")
    assert len(recipes) == 3

    documents = [yaml.safe_load(recipe) for recipe in recipes]
    assert all(isinstance(document, dict) for document in documents)
    assert all(
        document["triggers"][0]["event_type"] == "time_messenger_event" for document in documents
    )
    assert all(
        document["triggers"][0]["event_data"] == {"schema_version": 1, "type": "direct_message"}
        for document in documents
    )
    assert documents[0]["actions"][0]["action"] == "persistent_notification.create"
    assert documents[1]["actions"][0]["action"] == "light.turn_on"
    assert documents[1]["actions"][0]["data"]["flash"]
    assert documents[2]["actions"][0]["action"].startswith("tts.")
    assert "trim | length > 0" in recipes[2]
    assert "privacy opt-in" in markdown.lower()
    assert "замен" in markdown.lower() and "entity" in markdown.lower()
    assert "несколько ConfigEntry" in markdown
    assert "добавьте точный `config_entry_id`" in markdown
    assert "полное сообщение попадет в persistent notification" in markdown
    assert "лампа может просто включиться и остаться включенной" in markdown


def test_removal_and_support_do_not_overpromise_remote_cleanup() -> None:
    """Matrix: local removal is clear even when remote revoke is unavailable."""
    markdown = readme()
    removal = markdown[heading_position(markdown, "Удаление и поддержка") :]

    assert "credentials" in removal.lower()
    assert "dedupe" in removal.lower()
    assert "best effort" in removal.lower()
    assert "Session" in removal
    assert "OAuth" in removal and "PAT" in removal
    assert "remote revoke" in removal.lower() and "не обещ" in removal.lower()
    assert "redacted diagnostics" in removal.lower()
    assert ISSUES_URL in removal
    assert "завершите сессию вручную средствами tenant" in removal


def test_readme_meets_the_mechanical_humanizer_floor() -> None:
    """Keep obvious generated-writing artifacts out of the published README."""
    markdown = readme()

    assert chr(0x2014) not in markdown
    assert chr(0x2013) not in markdown
    assert " -- " not in markdown
    headings = re.findall(r"^#{1,3} .+$", markdown, re.MULTILINE)
    assert not any(
        0x2600 <= ord(character) <= 0x27BF
        or 0x1F1E6 <= ord(character) <= 0x1F1FF
        or 0x1F300 <= ord(character) <= 0x1FAFF
        for heading in headings
        for character in heading
    )
    assert not re.search(r"^[-*] \*\*[^*]+:\*\*", markdown, re.MULTILINE)
    forbidden_phrases = {
        "давайте разбер",
        "важно отметить",
        "ключевую роль",
        "не просто",
        "в заключение",
        "I hope this helps",
        "let me know",
    }
    assert all(phrase.lower() not in markdown.lower() for phrase in forbidden_phrases)


def test_repository_icon_is_a_valid_square_png() -> None:
    """The repository ships a real square bitmap rather than a renamed asset."""
    data = ICON_PATH.read_bytes()

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    assert width == height
    assert width >= 256
    assert bit_depth == 8
    assert color_type in {2, 6}
    assert len(data) > 1024

    offset = 8
    chunk_types: list[bytes] = []
    while offset < len(data):
        chunk_length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + chunk_length
        assert chunk_end <= len(data)
        chunk_data = data[offset + 8 : offset + 8 + chunk_length]
        expected_crc = struct.unpack(">I", data[offset + 8 + chunk_length : chunk_end])[0]
        assert zlib.crc32(chunk_type + chunk_data) == expected_crc
        chunk_types.append(chunk_type)
        offset = chunk_end
        if chunk_type == b"IEND":
            break

    assert offset == len(data)
    assert chunk_types[0] == b"IHDR"
    assert b"IDAT" in chunk_types
    assert chunk_types[-1] == b"IEND"
