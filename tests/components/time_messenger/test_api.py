"""Tests for the isolated Time v4 wire boundary."""

import asyncio
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientConnectionError, RequestInfo, WSMsgType, WSServerHandshakeError
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from custom_components.time_messenger.api.auth import StaticTokenProvider, token_from_oauth_data
from custom_components.time_messenger.api.client import (
    TimeApiClient,
    _parse_retry_after,
    normalize_tenant_origin,
    origin_url,
    parse_posted_event,
)
from custom_components.time_messenger.api.exceptions import (
    AuthError,
    ProtocolError,
    RateLimitError,
    TransientError,
    UnsupportedCapability,
)
from custom_components.time_messenger.api.websocket import TimeWebSocketClient, _reject_redirect
from custom_components.time_messenger.dedupe import DurableDedupe
from custom_components.time_messenger.event import HomeAssistantEventPublisher
from custom_components.time_messenger.pipeline import MessagePipeline

FIXTURES = Path(__file__).parents[2] / "fixtures" / "time_messenger"


def fixture_payload(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


class Response:
    def __init__(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers or {}
        self.released = False

    async def json(self, *, content_type: Any = None) -> Any:
        if self.payload is NO_CONTENT:
            raise ValueError("no content")
        return self.payload

    def release(self) -> None:
        self.released = True


class Session:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> Response:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


NO_CONTENT = object()


@pytest.mark.parametrize(
    "value",
    [
        "http://time.example",
        "https://user:pass@time.example",
        "https://time.example/api/v4",
        "https://time.example?token=x",
    ],
)
def test_origin_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_tenant_origin(value)


def test_origin_normalization_and_same_origin_url() -> None:
    assert normalize_tenant_origin("https://TIME.EXAMPLE:443/") == "https://time.example"
    assert origin_url("https://time.example", "/api/v4/users/me") == (
        "https://time.example/api/v4/users/me"
    )


@pytest.mark.parametrize("status", [200, 201])
async def test_session_login_accepts_user_json_from_any_2xx(status: int) -> None:
    headers = CIMultiDict({"token": "secret"})
    session = Session([Response(status, {"id": "me"}, headers)])
    client = TimeApiClient(session, "https://time.example", None)  # type: ignore[arg-type]
    token, user_id = await client.async_login("login", "password", "mfa")
    assert (token, user_id) == ("secret", "me")
    _, _, kwargs = session.calls[0]
    assert kwargs["allow_redirects"] is False
    assert kwargs["json"] == {"login_id": "login", "password": "password", "token": "mfa"}


async def test_session_login_204_uses_new_token_for_users_me() -> None:
    login_response = Response(204, NO_CONTENT, CIMultiDict({"tOkEn": "secret"}))
    me_response = Response(200, fixture_payload("users_me.json"))
    session = Session([login_response, me_response])
    client = TimeApiClient(session, "https://time.example", None)  # type: ignore[arg-type]
    token, user_id = await client.async_login("login", "password")
    assert (token, user_id) == ("secret", "user-redacted")
    assert session.calls[1][2]["headers"]["Authorization"] == "Bearer secret"
    assert login_response.released is True
    assert me_response.released is True


async def test_session_login_unusable_user_json_falls_back_to_users_me() -> None:
    session = Session(
        [
            Response(200, {"status": "ok"}, CIMultiDict({"Token": "secret"})),
            Response(200, fixture_payload("users_me.json")),
        ]
    )
    client = TimeApiClient(session, "https://time.example", None)  # type: ignore[arg-type]
    assert await client.async_login("login", "password") == ("secret", "user-redacted")


async def test_session_login_logs_out_if_users_me_fallback_fails() -> None:
    session = Session(
        [
            Response(204, NO_CONTENT, CIMultiDict({"Token": "secret"})),
            Response(503, {}),
            Response(200, {}),
        ]
    )
    client = TimeApiClient(session, "https://time.example", None)  # type: ignore[arg-type]
    with pytest.raises(TransientError):
        await client.async_login("login", "password")
    assert session.calls[-1][0:2] == (
        "POST",
        "https://time.example/api/v4/users/logout",
    )


async def test_login_without_token_is_protocol_error() -> None:
    session = Session([Response(200, {"id": "me"})])
    client = TimeApiClient(session, "https://time.example", None)  # type: ignore[arg-type]
    with pytest.raises(ProtocolError, match="Token"):
        await client.async_login("login", "password")


async def test_authenticated_rest_refuses_redirect_and_never_follows_it() -> None:
    response = Response(302, {}, {"Location": "https://evil.example/steal"})
    session = Session([response])
    client = TimeApiClient(
        session,
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    with pytest.raises(ProtocolError, match="redirect"):
        await client.async_get_me()
    assert len(session.calls) == 1
    assert session.calls[0][2]["headers"]["Authorization"] == "Bearer secret"


async def test_channel_type_uses_rest_backed_cache() -> None:
    session = Session([Response(200, {"type": "D"})])
    client = TimeApiClient(
        session,
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    assert await client.async_get_channel_type("c1") == "D"
    assert await client.async_get_channel_type("c1") == "D"
    assert len(session.calls) == 1


async def test_channel_id_is_escaped_inside_bound_endpoint() -> None:
    session = Session([Response(200, {"type": "D"})])
    client = TimeApiClient(
        session,
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    assert await client.async_get_channel_type("../users/me") == "D"
    assert session.calls[0][1].endswith("/api/v4/channels/..%2Fusers%2Fme")


async def test_disabled_capability_is_classified_as_unsupported() -> None:
    session = Session([Response(403, {})])
    client = TimeApiClient(
        session,
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    with pytest.raises(UnsupportedCapability):
        await client.async_get_me()


async def test_rate_limit_reset_header_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("custom_components.time_messenger.api.client.time.time", lambda: 100.0)
    session = Session([Response(429, {}, {"X-RateLimit-Reset": "112"})])
    client = TimeApiClient(
        session,
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    with pytest.raises(RateLimitError) as raised:
        await client.async_get_me()
    assert raised.value.retry_after == 12.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12.5", 12.5),
        ("Wed, 11 Aug 2026 12:00:30 GMT", 30.0),
        ("nan", None),
        ("inf", None),
        ("-inf", None),
        ("999999", 300.0),
    ],
)
def test_retry_after_parser_is_finite_and_bounded(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: float | None
) -> None:
    monkeypatch.setattr(
        "custom_components.time_messenger.api.client.time.time", lambda: 1_786_449_600
    )
    result = _parse_retry_after(value)
    if expected is None:
        assert result is None
    else:
        assert math.isclose(result, expected)


def posted(post_value: object, **data_values: object) -> dict[str, object]:
    return {"event": "posted", "data": {"post": post_value, **data_values}}


@pytest.mark.parametrize("as_string", [False, True])
def test_post_parser_accepts_object_or_json_string(as_string: bool) -> None:
    raw = {
        "id": "p1",
        "channel_id": "c1",
        "user_id": "u2",
        "type": "",
        "message": "private",
        "create_at": 1_755_000_000_000,
        "file_ids": ["f1"],
    }
    value: object = json.dumps(raw) if as_string else raw
    result = parse_posted_event(posted(value, channel_type="D", sender_name="alex"))
    assert result is not None
    assert result.post_id == "p1"
    assert result.channel_type == "D"
    assert result.file_ids == ("f1",)


@pytest.mark.parametrize(
    "payload",
    [
        {"event": "hello", "data": {}},
        posted("not json"),
        posted({"id": "p1"}),
        posted(
            {
                "id": "p1",
                "channel_id": "c1",
                "user_id": "u2",
                "type": None,
                "message": "x",
                "create_at": 1,
            }
        ),
    ],
)
def test_malformed_or_unknown_events_are_dropped(payload: dict[str, object]) -> None:
    assert parse_posted_event(payload) is None


def test_timestamp_outside_datetime_range_is_dropped() -> None:
    payload = fixture_payload("posted_direct.json")
    raw_post = json.loads(payload["data"]["post"])
    raw_post["create_at"] = 10**30
    payload["data"]["post"] = json.dumps(raw_post)
    assert parse_posted_event(payload) is None


async def test_websocket_redirect_trace_aborts_handshake() -> None:
    with pytest.raises(ProtocolError, match="redirect"):
        await _reject_redirect(AsyncMock(), None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "responses",
    [
        [
            fixture_payload("hello.json"),
            {"status": "OK", "seq_reply": 1},
        ],
        [
            {"status": "OK", "seq_reply": 1},
            fixture_payload("hello.json"),
        ],
    ],
)
async def test_websocket_auth_requires_ack_and_hello_in_either_order(
    responses: list[dict[str, Any]],
) -> None:
    socket = SimpleNamespace(
        send_json=AsyncMock(),
        receive=AsyncMock(
            side_effect=[
                SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(response))
                for response in responses
            ]
        ),
    )
    client = TimeWebSocketClient(
        AsyncMock(),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    await client._async_authenticate(socket)
    socket.send_json.assert_awaited_once_with(
        {"seq": 1, "action": "authentication_challenge", "data": {"token": "secret"}}
    )
    assert socket.receive.await_count == 2
    assert client.server_version == "REDACTED_VERSION"


async def test_websocket_auth_fail_is_terminal_auth_error() -> None:
    socket = SimpleNamespace(
        send_json=AsyncMock(),
        receive=AsyncMock(
            return_value=SimpleNamespace(
                type=WSMsgType.TEXT,
                data=json.dumps({"status": "FAIL", "seq_reply": 1}),
            )
        ),
    )
    client = TimeWebSocketClient(
        AsyncMock(),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    with pytest.raises(AuthError):
        await client._async_authenticate(socket)


async def test_websocket_send_failure_is_normalized() -> None:
    socket = SimpleNamespace(send_json=AsyncMock(side_effect=ClientConnectionError("closed")))
    client = TimeWebSocketClient(
        AsyncMock(),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    with pytest.raises(TransientError):
        await client._async_authenticate(socket)


async def test_websocket_receive_failure_is_normalized() -> None:
    socket = SimpleNamespace(
        send_json=AsyncMock(),
        receive=AsyncMock(side_effect=ClientConnectionError("closed")),
    )
    client = TimeWebSocketClient(
        AsyncMock(),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    with pytest.raises(TransientError):
        await client._async_authenticate(socket)


def handshake_error(status: int, headers: dict[str, str] | None = None) -> WSServerHandshakeError:
    response_headers = CIMultiDictProxy(CIMultiDict(headers or {}))
    request_info = RequestInfo(
        URL("wss://time.example/api/v4/websocket"),
        "GET",
        response_headers,
        URL("wss://time.example/api/v4/websocket"),
    )
    return WSServerHandshakeError(
        request_info,
        (),
        status=status,
        message="redacted",
        headers=response_headers,
    )


@pytest.mark.parametrize(
    ("status", "headers", "error_type", "retry_after"),
    [
        (401, {}, AuthError, None),
        (403, {}, UnsupportedCapability, None),
        (429, {"Retry-After": "17"}, RateLimitError, 17.0),
        (429, {"Retry-After": "999999"}, RateLimitError, 300.0),
        (503, {}, TransientError, None),
    ],
)
async def test_websocket_handshake_failures_are_classified(
    status: int,
    headers: dict[str, str],
    error_type: type[Exception],
    retry_after: float | None,
) -> None:
    session = SimpleNamespace(ws_connect=AsyncMock(side_effect=handshake_error(status, headers)))
    client = TimeWebSocketClient(
        session,
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    with pytest.raises(error_type) as raised:
        await client._async_connect()
    if isinstance(raised.value, RateLimitError):
        assert raised.value.retry_after == retry_after


class MemoryStore:
    async def async_load(self) -> None:
        return None

    async def async_save(self, _data: Any) -> None:
        return None


class FiniteSocket:
    def __init__(self, auth_messages: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
        self._auth_messages = iter(auth_messages)
        self._events = events
        self.closed = False
        self._response = SimpleNamespace(url=URL("wss://time.example/api/v4/websocket"))

    async def send_json(self, _payload: dict[str, Any]) -> None:
        return None

    async def receive(self) -> Any:
        return SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(next(self._auth_messages)))

    def __aiter__(self) -> Any:
        async def iterator() -> Any:
            for event in self._events:
                yield SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(event))

        return iterator()

    async def close(self) -> None:
        self.closed = True


async def test_async_listen_delivers_fixture_post_through_real_event_boundary() -> None:
    fired: list[tuple[str, dict[str, object]]] = []

    class Hass:
        def __init__(self) -> None:
            self.bus = SimpleNamespace(async_fire=lambda event, data: fired.append((event, data)))
            self.data: dict[str, object] = {}

        def verify_event_loop_thread(self, _action: str) -> None:
            pass

    hass = Hass()
    publisher = HomeAssistantEventPublisher(
        hass,
        config_entry_id="entry",
        account_user_id="me",
        include_message_text=False,
    )
    pipeline = MessagePipeline(
        account_user_id="me",
        resolve_channel_type=AsyncMock(return_value="D"),
        dedupe=DurableDedupe(MemoryStore(), now=lambda: 1000),
        publish=publisher.async_publish,
    )
    socket = FiniteSocket(
        [fixture_payload("hello.json"), {"status": "OK", "seq_reply": 1}],
        [fixture_payload("posted_direct.json")],
    )
    client = TimeWebSocketClient(
        SimpleNamespace(),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
    )
    client._async_connect = AsyncMock(return_value=socket)  # type: ignore[method-assign]
    await client.async_listen(pipeline.async_process, lambda: True)
    assert fired == [
        (
            "time_messenger_event",
            {
                "schema_version": 1,
                "type": "direct_message",
                "config_entry_id": "entry",
                "account_user_id": "me",
                "post_id": "post-redacted",
                "channel_id": "channel-redacted",
                "sender_user_id": "sender-redacted",
                "message_text": None,
                "text_redacted": True,
                "created_at": "2025-08-12T12:00:00Z",
                "sender_username": "REDACTED",
            },
        )
    ]


async def test_channel_cache_evicts_least_recently_used_entry() -> None:
    session = Session(
        [
            Response(200, {"type": "D"}),
            Response(200, {"type": "G"}),
            Response(200, {"type": "P"}),
            Response(200, {"type": "D"}),
        ]
    )
    client = TimeApiClient(
        session,
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
        channel_cache_size=2,
    )
    assert await client.async_get_channel_type("c1") == "D"
    assert await client.async_get_channel_type("c2") == "G"
    assert await client.async_get_channel_type("c3") == "P"
    assert await client.async_get_channel_type("c1") == "D"
    assert len(session.calls) == 4


def test_oauth_token_type_must_be_a_string() -> None:
    with pytest.raises(ProtocolError, match="token type"):
        token_from_oauth_data({"access_token": "secret", "token_type": 123})


async def test_rest_request_timeout_is_normalized() -> None:
    async def hang(*_args: Any, **_kwargs: Any) -> Any:
        await asyncio.Event().wait()

    client = TimeApiClient(
        SimpleNamespace(request=hang),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
        request_timeout=0.01,
    )
    with pytest.raises(TransientError):
        await client.async_get_me()


async def test_rest_token_provider_is_inside_request_timeout() -> None:
    async def hang() -> str:
        await asyncio.Event().wait()
        return "unreachable"

    provider = SimpleNamespace(async_get_token=hang)
    session = SimpleNamespace(request=AsyncMock())
    client = TimeApiClient(
        session,
        "https://time.example",
        provider,  # type: ignore[arg-type]
        request_timeout=0.01,
    )
    with pytest.raises(TransientError):
        await asyncio.wait_for(client.async_get_me(), timeout=0.1)
    session.request.assert_not_awaited()


async def test_websocket_connect_timeout_is_normalized() -> None:
    async def hang(*_args: Any, **_kwargs: Any) -> Any:
        await asyncio.Event().wait()

    client = TimeWebSocketClient(
        SimpleNamespace(ws_connect=hang),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
        connect_timeout=0.01,
    )
    with pytest.raises(TransientError):
        await client._async_connect()


async def test_websocket_token_getter_is_inside_auth_timeout() -> None:
    provider = SimpleNamespace(async_get_token=AsyncMock(side_effect=RuntimeError("provider")))
    client = TimeWebSocketClient(
        SimpleNamespace(),
        "https://time.example",
        provider,  # type: ignore[arg-type]
        auth_timeout=0.01,
    )
    with pytest.raises(AuthError):
        await client._async_authenticate(SimpleNamespace(send_json=AsyncMock()))


async def test_websocket_close_is_bounded_when_peer_hangs() -> None:
    class HangingSocket:
        closed = False

        async def close(self) -> None:
            await asyncio.Event().wait()

    client = TimeWebSocketClient(
        SimpleNamespace(),
        "https://time.example",
        StaticTokenProvider("secret"),  # type: ignore[arg-type]
        close_timeout=0.01,
    )
    client._socket = HangingSocket()
    await asyncio.wait_for(client.async_close(), timeout=0.1)
