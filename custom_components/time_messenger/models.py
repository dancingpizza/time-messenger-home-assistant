"""Immutable domain models and ports for Time Messenger."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CanonicalPost:
    """A defensively decoded Time post, before domain filtering."""

    post_id: str
    channel_id: str
    sender_user_id: str
    post_type: str
    message: str
    created_at: str
    channel_type: str | None = None
    sender_username: str | None = None
    root_id: str | None = None
    file_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DirectMessage:
    """Canonical direct message accepted by the domain pipeline."""

    post_id: str
    channel_id: str
    sender_user_id: str
    message: str
    created_at: str
    sender_username: str | None = None
    root_id: str | None = None
    file_ids: tuple[str, ...] = ()


class TokenProvider(Protocol):
    """Port implemented by explicit authentication adapters."""

    async def async_get_token(self) -> str:
        """Return the current bearer token."""


class DedupePort(Protocol):
    """Persistent check-and-mark port."""

    async def async_check_and_mark(self, post_id: str) -> bool:
        """Return true only when the id was durably recorded for the first time."""


type ChannelTypeResolver = Callable[[str], Awaitable[str | None]]
type EventPublisher = Callable[[DirectMessage], Awaitable[None]]
type EventData = Mapping[str, object]
