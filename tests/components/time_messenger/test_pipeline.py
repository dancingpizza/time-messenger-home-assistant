"""Tests for fail-closed direct-message filtering."""

from unittest.mock import AsyncMock

import pytest

from custom_components.time_messenger.models import CanonicalPost
from custom_components.time_messenger.pipeline import MessagePipeline, classify_direct_message


def post(**changes: object) -> CanonicalPost:
    values = {
        "post_id": "p1",
        "channel_id": "c1",
        "sender_user_id": "other",
        "post_type": "",
        "message": "private text",
        "created_at": "2026-08-11T12:00:00Z",
        "channel_type": "D",
    }
    values.update(changes)
    return CanonicalPost(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "candidate",
    [
        post(sender_user_id="me"),
        post(post_type="system_generic"),
        post(channel_type="G"),
        post(channel_type="P"),
        post(channel_type="O"),
    ],
)
async def test_self_system_and_non_direct_posts_are_dropped(candidate: CanonicalPost) -> None:
    resolver = AsyncMock(return_value="D")
    assert (
        await classify_direct_message(
            candidate, account_user_id="me", resolve_channel_type=resolver
        )
        is None
    )
    resolver.assert_not_awaited()


async def test_missing_channel_type_is_resolved() -> None:
    resolver = AsyncMock(return_value="D")
    message = await classify_direct_message(
        post(channel_type=None), account_user_id="me", resolve_channel_type=resolver
    )
    assert message is not None
    resolver.assert_awaited_once_with("c1")


async def test_channel_lookup_failure_drops_fail_closed() -> None:
    resolver = AsyncMock(side_effect=RuntimeError("offline"))
    assert (
        await classify_direct_message(
            post(channel_type=None), account_user_id="me", resolve_channel_type=resolver
        )
        is None
    )


async def test_pipeline_marks_before_publication_and_suppresses_duplicate() -> None:
    order: list[str] = []
    dedupe = AsyncMock()
    dedupe.async_check_and_mark.side_effect = lambda _post_id: order.append("save") or True

    async def publish(_message: object) -> None:
        order.append("publish")

    pipeline = MessagePipeline(
        account_user_id="me",
        resolve_channel_type=AsyncMock(return_value="D"),
        dedupe=dedupe,
        publish=publish,
    )
    assert await pipeline.async_process(post()) is True
    assert order == ["save", "publish"]
    dedupe.async_check_and_mark.return_value = False
    dedupe.async_check_and_mark.side_effect = None
    assert await pipeline.async_process(post()) is False


async def test_pipeline_drops_when_durable_store_fails() -> None:
    dedupe = AsyncMock()
    dedupe.async_check_and_mark.side_effect = OSError("disk unavailable")
    publish = AsyncMock()
    pipeline = MessagePipeline(
        account_user_id="me",
        resolve_channel_type=AsyncMock(return_value="D"),
        dedupe=dedupe,
        publish=publish,
    )
    assert await pipeline.async_process(post()) is False
    publish.assert_not_awaited()
