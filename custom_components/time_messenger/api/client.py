"""Redirect-safe asynchronous Time REST v4 client."""

from __future__ import annotations

import asyncio
import ipaddress
import math
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from ..const import CHANNEL_CACHE_MAX_ENTRIES, MAX_RETRY_DELAY, REST_REQUEST_TIMEOUT
from ..models import CanonicalPost, TokenProvider
from .auth import StaticTokenProvider
from .exceptions import (
    AuthError,
    ProtocolError,
    RateLimitError,
    TimeMessengerError,
    TransientError,
    UnsupportedCapability,
)


def normalize_tenant_origin(value: str, *, allow_loopback_http: bool = False) -> str:
    """Return a safe origin with no path, query, credentials, or fragment."""

    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as err:
        raise ValueError("invalid tenant origin") from err
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("tenant origin must contain only a host")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("tenant origin must not contain a path, query, or fragment")
    scheme = parsed.scheme.lower()
    is_loopback = _is_loopback(parsed.hostname)
    if scheme != "https" and not (scheme == "http" and allow_loopback_http and is_loopback):
        raise ValueError("tenant origin must use HTTPS")
    host = parsed.hostname.lower().rstrip(".")
    if ":" in host:
        host = f"[{host}]"
    default_port = 443 if scheme == "https" else 80
    netloc = host if port in (None, default_port) else f"{host}:{port}"
    return urlunsplit((scheme, netloc, "", "", ""))


def _is_loopback(host: str) -> bool:
    if host.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def origin_url(origin: str, path: str) -> str:
    """Build a URL while proving it remains on the bound origin."""

    url = urljoin(f"{origin}/", path.lstrip("/"))
    parsed_origin = urlsplit(origin)
    parsed_url = urlsplit(url)
    if (parsed_url.scheme, parsed_url.netloc) != (parsed_origin.scheme, parsed_origin.netloc):
        raise ValueError("request URL escaped tenant origin")
    return url


class TimeApiClient:
    """The only production adapter that knows the Time REST wire contract."""

    def __init__(
        self,
        session: ClientSession,
        origin: str,
        token_provider: TokenProvider | None,
        *,
        request_timeout: float = REST_REQUEST_TIMEOUT,
        channel_cache_size: int = CHANNEL_CACHE_MAX_ENTRIES,
    ) -> None:
        self._session = session
        self.origin = normalize_tenant_origin(origin)
        self._token_provider = token_provider
        self._request_timeout = request_timeout
        self._channel_cache_size = max(1, channel_cache_size)
        self._channel_cache: OrderedDict[str, str] = OrderedDict()

    async def async_login(
        self, login_id: str, password: str, mfa_code: str | None = None
    ) -> tuple[str, str]:
        """Create a Time session and return only bearer and immutable user id."""

        body: dict[str, str] = {"login_id": login_id, "password": password}
        if mfa_code:
            body["token"] = mfa_code
        response = await self._request(
            "POST", "/api/v4/users/login", json=body, authenticated=False
        )
        token = response.headers.get("Token")
        if not isinstance(token, str) or not token:
            response.release()
            raise ProtocolError("session login response has no Token header")
        payload: dict[str, Any] = {}
        if response.status == 204:
            response.release()
        else:
            try:
                payload = await _json_object(response)
            except ProtocolError:
                pass
        user_id = payload.get("id")
        if not isinstance(user_id, str) or not user_id:
            authenticated = TimeApiClient(
                self._session,
                self.origin,
                StaticTokenProvider(token),
                request_timeout=self._request_timeout,
                channel_cache_size=self._channel_cache_size,
            )
            try:
                me = await authenticated.async_get_me()
            except TimeMessengerError:
                try:
                    await authenticated.async_logout()
                except TimeMessengerError:
                    pass
                raise
            user_id = me["id"]
        return token, user_id

    async def async_get_me(self) -> Mapping[str, Any]:
        response = await self._request("GET", "/api/v4/users/me")
        payload = await _json_object(response)
        if not isinstance(payload.get("id"), str) or not payload["id"]:
            raise ProtocolError("users/me response has no user id")
        return payload

    async def async_set_online(
        self,
        bound_user_id: str,
        *,
        request_guard: Callable[[], bool] | None = None,
    ) -> bool:
        """Set the bound account online if allowed immediately before sending."""

        try:
            response = await self._request(
                "PUT",
                "/api/v4/users/me/status",
                json={"user_id": bound_user_id, "status": "online"},
                request_guard=request_guard,
            )
        except _RequestSuppressed:
            return False
        payload = await _json_object(response)
        if payload.get("user_id") != bound_user_id or payload.get("status") != "online":
            raise ProtocolError("user status response did not confirm bound user online")
        return True

    async def async_get_channel_type(self, channel_id: str) -> str | None:
        cached = self._channel_cache.get(channel_id)
        if cached is not None:
            self._channel_cache.move_to_end(channel_id)
            return cached
        response = await self._request("GET", f"/api/v4/channels/{quote(channel_id, safe='')}")
        payload = await _json_object(response)
        channel_type = payload.get("type")
        if not isinstance(channel_type, str) or channel_type not in {"D", "G", "P", "O"}:
            raise ProtocolError("channel response has an invalid type")
        self._channel_cache[channel_id] = channel_type
        self._channel_cache.move_to_end(channel_id)
        while len(self._channel_cache) > self._channel_cache_size:
            self._channel_cache.popitem(last=False)
        return channel_type

    async def async_logout(self) -> None:
        response = await self._request("POST", "/api/v4/users/logout")
        response.release()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        request_guard: Callable[[], bool] | None = None,
        **kwargs: Any,
    ) -> ClientResponse:
        headers = dict(kwargs.pop("headers", {}))
        kwargs.setdefault("timeout", ClientTimeout(total=self._request_timeout))
        try:
            async with asyncio.timeout(self._request_timeout):
                if authenticated:
                    if self._token_provider is None:
                        raise ProtocolError("authenticated request has no token provider")
                    token = await self._token_provider.async_get_token()
                    headers["Authorization"] = f"Bearer {token}"
                if request_guard is not None and not request_guard():
                    raise _RequestSuppressed
                response = await self._session.request(
                    method,
                    origin_url(self.origin, path),
                    headers=headers,
                    allow_redirects=False,
                    **kwargs,
                )
        except (TimeoutError, ClientError) as err:
            raise TransientError("Time API request failed") from err
        if 300 <= response.status < 400:
            response.release()
            raise ProtocolError("Time API redirect refused")
        if response.status == 401:
            response.release()
            raise AuthError("Time API rejected credentials")
        if response.status == 403:
            response.release()
            raise UnsupportedCapability("Time API capability is disabled")
        if response.status == 429:
            retry_after = _rate_limit_delay(response.headers)
            response.release()
            raise RateLimitError(retry_after)
        if response.status >= 500:
            response.release()
            raise TransientError("Time API server error")
        if response.status >= 400:
            response.release()
            raise ProtocolError(f"Time API returned HTTP {response.status}")
        return response


class _RequestSuppressed(Exception):
    """The caller's last-moment guard intentionally prevented a request."""


async def _json_object(response: ClientResponse) -> dict[str, Any]:
    try:
        try:
            payload = await response.json(content_type=None)
        except (ValueError, ClientError) as err:
            raise ProtocolError("Time API returned invalid JSON") from err
        if not isinstance(payload, dict):
            raise ProtocolError("Time API returned a non-object response")
        return payload
    finally:
        response.release()


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except TypeError, ValueError, OverflowError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        delay = parsed.timestamp() - time.time()
    if not math.isfinite(delay):
        return None
    return min(MAX_RETRY_DELAY, max(0.0, delay))


def _rate_limit_delay(headers: Mapping[str, str]) -> float | None:
    retry_after = _parse_retry_after(headers.get("Retry-After"))
    if retry_after is not None:
        return retry_after
    reset = headers.get("X-RateLimit-Reset") or headers.get("X-Ratelimit-Reset")
    if reset is None:
        return None
    try:
        delay = float(reset) - time.time()
    except ValueError, OverflowError:
        return None
    if not math.isfinite(delay):
        return None
    return min(MAX_RETRY_DELAY, max(0.0, delay))


def parse_posted_event(payload: Mapping[str, Any]) -> CanonicalPost | None:
    """Defensively decode only Time's `posted` wire event."""

    if payload.get("event") != "posted":
        return None
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None
    raw_post = data.get("post")
    if isinstance(raw_post, str):
        import json

        try:
            raw_post = json.loads(raw_post)
        except TypeError, ValueError:
            return None
    if not isinstance(raw_post, Mapping):
        return None

    def required_string(key: str) -> str | None:
        value = raw_post.get(key)
        return value if isinstance(value, str) and value else None

    post_id = required_string("id")
    channel_id = required_string("channel_id")
    sender_user_id = required_string("user_id")
    if not post_id or not channel_id or not sender_user_id:
        return None
    post_type = raw_post.get("type")
    message = raw_post.get("message")
    create_at = raw_post.get("create_at")
    if not isinstance(post_type, str) or not isinstance(message, str):
        return None
    if not isinstance(create_at, int) or isinstance(create_at, bool) or create_at < 0:
        return None
    channel_type = data.get("channel_type")
    if not isinstance(channel_type, str) or channel_type not in {"D", "G", "P", "O"}:
        channel_type = None
    sender_username = data.get("sender_name")
    if not isinstance(sender_username, str) or not sender_username:
        sender_username = None
    root_id = raw_post.get("root_id")
    if not isinstance(root_id, str) or not root_id:
        root_id = None
    file_ids_value = raw_post.get("file_ids")
    file_ids = (
        tuple(value for value in file_ids_value if isinstance(value, str) and value)
        if isinstance(file_ids_value, list)
        else ()
    )
    try:
        created_at = (
            datetime.fromtimestamp(create_at / 1000, tz=UTC).isoformat().replace("+00:00", "Z")
        )
    except OSError, OverflowError, ValueError:
        return None
    return CanonicalPost(
        post_id=post_id,
        channel_id=channel_id,
        sender_user_id=sender_user_id,
        post_type=post_type,
        message=message,
        created_at=created_at,
        channel_type=channel_type,
        sender_username=sender_username,
        root_id=root_id,
        file_ids=file_ids,
    )
