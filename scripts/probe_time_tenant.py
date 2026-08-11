#!/usr/bin/env python3
"""Manual AD-12 acceptance probe; never prints credentials or message content."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

from aiohttp import ClientSession, TraceConfig, WSMsgType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from custom_components.time_messenger.api.auth import StaticTokenProvider  # noqa: E402
from custom_components.time_messenger.api.client import (  # noqa: E402
    TimeApiClient,
    normalize_tenant_origin,
)
from custom_components.time_messenger.api.exceptions import TimeMessengerError  # noqa: E402
from custom_components.time_messenger.api.websocket import (  # noqa: E402
    TimeWebSocketClient,
    _reject_redirect,
)


def tenant_origin(value: str) -> str:
    try:
        return normalize_tenant_origin(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from err


def positive_finite_duration(value: str) -> float:
    try:
        duration = float(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError("duration must be a number") from err
    if not math.isfinite(duration) or duration <= 0:
        raise argparse.ArgumentTypeError("duration must be finite and greater than zero")
    return duration


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe users/me, authenticated hello, and redacted posted-event classes."
    )
    parser.add_argument("--origin", required=True, type=tenant_origin, help="HTTPS tenant origin")
    parser.add_argument("--auth-mode", choices=("oauth", "pat", "session"), required=True)
    parser.add_argument(
        "--duration", type=positive_finite_duration, default=60.0, help="Observation seconds"
    )
    parser.add_argument("--login", help="Session login (or TIME_MESSENGER_LOGIN); never printed")
    return parser.parse_args()


async def token_for(args: argparse.Namespace, session: ClientSession, origin: str) -> str:
    if args.auth_mode in {"oauth", "pat"}:
        token = os.environ.get("TIME_MESSENGER_TOKEN")
        if not token:
            token = await asyncio.to_thread(getpass.getpass, "Bearer token: ")
        return token
    login = args.login or os.environ.get("TIME_MESSENGER_LOGIN")
    if not login:
        login = await asyncio.to_thread(input, "Login: ")
    password = await asyncio.to_thread(getpass.getpass, "Password: ")
    mfa = await asyncio.to_thread(getpass.getpass, "MFA code (blank if unused): ")
    client = TimeApiClient(session, origin, None)
    token, _user_id = await client.async_login(login, password, mfa or None)
    return token


async def run(args: argparse.Namespace) -> int:
    origin = normalize_tenant_origin(args.origin)
    trace = TraceConfig()
    trace.on_request_redirect.append(_reject_redirect)
    counts: Counter[str] = Counter()
    async with ClientSession(trace_configs=[trace]) as session:
        try:
            token = await token_for(args, session, origin)
            provider = StaticTokenProvider(token)
            api = TimeApiClient(session, origin, provider)
            me = await api.async_get_me()
            websocket = TimeWebSocketClient(session, origin, provider)
            socket = await websocket._async_connect()
            try:
                await websocket._async_authenticate(socket)
                print("PASS identity + authenticated hello")
                deadline = asyncio.get_running_loop().time() + args.duration
                while asyncio.get_running_loop().time() < deadline:
                    timeout = deadline - asyncio.get_running_loop().time()
                    try:
                        message = await asyncio.wait_for(socket.receive(), timeout=timeout)
                    except TimeoutError:
                        break
                    if message.type != WSMsgType.TEXT:
                        break
                    try:
                        payload = json.loads(message.data)
                    except TypeError, ValueError:
                        counts["malformed"] += 1
                        continue
                    if not isinstance(payload, dict) or payload.get("event") != "posted":
                        continue
                    data = payload.get("data")
                    channel_type = data.get("channel_type") if isinstance(data, dict) else None
                    counts[str(channel_type) if channel_type else "unknown"] += 1
                    raw_post = data.get("post") if isinstance(data, dict) else None
                    if isinstance(raw_post, str):
                        try:
                            raw_post = json.loads(raw_post)
                        except ValueError:
                            raw_post = None
                    if isinstance(raw_post, dict) and raw_post.get("user_id") == me["id"]:
                        counts["self"] += 1
            finally:
                await socket.close()
                if args.auth_mode == "session":
                    try:
                        await api.async_logout()
                    except TimeMessengerError:
                        pass
        except (TimeMessengerError, ValueError) as err:
            print(f"FAIL {type(err).__name__}", file=sys.stderr)
            return 1
    print("Observed redacted classes:", dict(sorted(counts.items())))
    print("Manual gate: verify D, G/P/O, self, reconnect replay, and every enabled auth mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(arguments())))
