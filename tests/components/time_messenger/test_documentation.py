"""Checks for copyable README examples and repository assets."""

import re
import struct
import zlib
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).parents[3]
README_PATH = REPOSITORY_ROOT / "README.md"
ICON_PATH = REPOSITORY_ROOT / "brand" / "icon.png"


def readme() -> str:
    """Read the user-facing documentation."""
    return README_PATH.read_text(encoding="utf-8")


def fenced_blocks(markdown: str, language: str) -> list[str]:
    """Extract fenced code blocks with the requested language."""
    return re.findall(rf"```{language}\n(.*?)\n```", markdown, re.DOTALL)


def test_readme_automation_example_is_parseable() -> None:
    """Catch malformed YAML or an example wired to the wrong event."""
    markdown = readme()
    recipes = fenced_blocks(markdown, "yaml")
    assert len(recipes) == 1

    document = yaml.safe_load(recipes[0])
    assert isinstance(document, dict)
    assert document["triggers"][0]["event_type"] == "time_messenger_event"
    assert document["actions"][0]["action"] == "persistent_notification.create"


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
