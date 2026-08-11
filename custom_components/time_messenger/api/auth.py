"""Explicit Time authentication adapters."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .exceptions import ProtocolError


@dataclass(slots=True, repr=False)
class StaticTokenProvider:
    """PAT or session bearer provider that never exposes its value in repr."""

    _token: str = field(repr=False)

    async def async_get_token(self) -> str:
        return self._token


@dataclass(slots=True, repr=False)
class OAuthTokenProvider:
    """Adapter around the Home Assistant OAuth token accessor."""

    _token_getter: Callable[[], Awaitable[str]] = field(repr=False)

    async def async_get_token(self) -> str:
        token = await self._token_getter()
        if not token:
            raise ProtocolError("OAuth provider returned no access token")
        return token


def token_from_oauth_data(token_data: dict[str, Any]) -> str:
    """Extract an OAuth bearer without accepting implicit fragments."""

    token = token_data.get("access_token")
    if not isinstance(token, str) or not token:
        raise ProtocolError("OAuth response has no access token")
    token_type = token_data.get("token_type", "bearer")
    if not isinstance(token_type, str) or token_type.lower() != "bearer":
        raise ProtocolError("OAuth response uses an unsupported token type")
    return token
