"""Authenticated, redirect-refusing Time WebSocket adapter."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from aiohttp import (
    ClientError,
    ClientSession,
    ClientWSTimeout,
    TraceConfig,
    WSMsgType,
    WSServerHandshakeError,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from ..const import WS_AUTH_TIMEOUT, WS_CLOSE_TIMEOUT, WS_CONNECT_TIMEOUT
from ..models import CanonicalPost, TokenProvider
from .client import _parse_retry_after, origin_url, parse_posted_event
from .exceptions import (
    AuthError,
    ProtocolError,
    RateLimitError,
    TransientError,
    UnsupportedCapability,
)

PostCallback = Callable[[CanonicalPost], Awaitable[None]]
GenerationGuard = Callable[[], bool]


async def _reject_redirect(_session: ClientSession, _trace_context: Any, _params: Any) -> None:
    raise ProtocolError("WebSocket redirect refused")


def create_time_session(hass: Any) -> ClientSession:
    """Create an entry-owned HA session that aborts every redirect."""

    trace = TraceConfig()
    trace.on_request_redirect.append(_reject_redirect)
    return async_create_clientsession(
        hass,
        auto_cleanup=False,
        trace_configs=[trace],
        raise_for_status=False,
    )


def release_time_session(session: Any) -> None:
    """Release a HA-created session without closing its shared connector."""

    if not getattr(session, "closed", False):
        session.detach()


async def _async_close_socket(socket: Any, close_timeout: float) -> None:
    try:
        async with asyncio.timeout(close_timeout):
            await socket.close()
    except TimeoutError, ClientError:
        pass


class TimeWebSocketClient:
    """Perform Time's challenge exchange and decode posted events."""

    def __init__(
        self,
        session: ClientSession,
        origin: str,
        token_provider: TokenProvider,
        *,
        connect_timeout: float = WS_CONNECT_TIMEOUT,
        auth_timeout: float = WS_AUTH_TIMEOUT,
        close_timeout: float = WS_CLOSE_TIMEOUT,
    ) -> None:
        self._session = session
        self._origin = origin
        self._token_provider = token_provider
        self._connect_timeout = connect_timeout
        self._auth_timeout = auth_timeout
        self._close_timeout = close_timeout
        self.server_version: str | None = None
        self._socket: Any = None

    @property
    def websocket_url(self) -> str:
        url = origin_url(self._origin, "/api/v4/websocket")
        scheme = "wss" if urlsplit(url).scheme == "https" else "ws"
        parsed = urlsplit(url)
        return parsed._replace(scheme=scheme).geturl()

    async def async_probe_hello(self) -> str | None:
        """Complete the capability gate without creating a listener task."""

        socket = await self._async_connect()
        try:
            await self._async_authenticate(socket)
            return self.server_version
        finally:
            await _async_close_socket(socket, self._close_timeout)
            self._socket = None

    async def async_listen(
        self,
        on_post: PostCallback,
        generation_alive: GenerationGuard,
    ) -> float:
        """Listen until disconnected and return healthy connection duration."""

        socket = await self._async_connect()
        connected_at = time.monotonic()
        try:
            await self._async_authenticate(socket)
            async for message in socket:
                if not generation_alive():
                    return time.monotonic() - connected_at
                if message.type == WSMsgType.TEXT:
                    try:
                        payload = json.loads(message.data)
                    except TypeError, ValueError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("status") == "FAIL" and payload.get("seq_reply") == 1:
                        raise AuthError("WebSocket rejected credentials")
                    post = parse_posted_event(payload)
                    if post is not None and generation_alive():
                        await on_post(post)
                elif message.type in {WSMsgType.ERROR, WSMsgType.CLOSED, WSMsgType.CLOSE}:
                    break
            return time.monotonic() - connected_at
        finally:
            await _async_close_socket(socket, self._close_timeout)
            self._socket = None

    async def async_close(self) -> None:
        socket = self._socket
        if socket is not None and not socket.closed:
            await _async_close_socket(socket, self._close_timeout)
        self._socket = None

    async def _async_connect(self) -> Any:
        try:
            async with asyncio.timeout(self._connect_timeout):
                socket = await self._session.ws_connect(
                    self.websocket_url,
                    autoclose=True,
                    timeout=ClientWSTimeout(ws_close=self._close_timeout),
                )
        except ProtocolError:
            raise
        except WSServerHandshakeError as err:
            if err.status == 401:
                raise AuthError("WebSocket rejected credentials") from err
            if err.status == 403:
                raise UnsupportedCapability("Time WebSocket capability is disabled") from err
            if err.status == 429:
                retry_after = err.headers.get("Retry-After") if err.headers else None
                raise RateLimitError(_parse_retry_after(retry_after)) from err
            if err.status >= 500:
                raise TransientError("WebSocket server error") from err
            raise ProtocolError(f"WebSocket handshake failed with HTTP {err.status}") from err
        except (TimeoutError, ClientError) as err:
            raise TransientError("WebSocket connection failed") from err
        response_url = socket._response.url  # aiohttp exposes the final handshake URL here.
        expected = urlsplit(self.websocket_url)
        actual = urlsplit(str(response_url))
        if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
            await _async_close_socket(socket, self._close_timeout)
            raise ProtocolError("WebSocket origin changed")
        self._socket = socket
        return socket

    async def _async_authenticate(self, socket: Any) -> None:
        try:
            async with asyncio.timeout(self._auth_timeout):
                try:
                    token = await self._token_provider.async_get_token()
                except AuthError:
                    raise
                except Exception as err:
                    raise AuthError("WebSocket token provider failed") from err
                await socket.send_json(
                    {
                        "seq": 1,
                        "action": "authentication_challenge",
                        "data": {"token": token},
                    }
                )
                acknowledged = False
                hello_received = False
                while not (acknowledged and hello_received):
                    message = await socket.receive()
                    if message.type != WSMsgType.TEXT:
                        raise TransientError("WebSocket closed before authentication")
                    try:
                        payload = json.loads(message.data)
                    except TypeError, ValueError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("status") == "FAIL" and payload.get("seq_reply") == 1:
                        raise AuthError("WebSocket rejected credentials")
                    if payload.get("status") == "OK" and payload.get("seq_reply") == 1:
                        acknowledged = True
                    if payload.get("event") == "hello":
                        hello_received = True
                        data = payload.get("data")
                        if isinstance(data, dict) and isinstance(data.get("server_version"), str):
                            self.server_version = data["server_version"]
        except TimeoutError as err:
            raise TransientError("WebSocket authentication timed out") from err
        except AuthError, TransientError:
            raise
        except ClientError as err:
            raise TransientError("WebSocket authentication failed") from err
        except Exception as err:
            raise TransientError("WebSocket authentication failed") from err
