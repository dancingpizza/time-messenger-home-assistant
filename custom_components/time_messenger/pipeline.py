"""Pure direct-message filtering and pipeline orchestration."""

from .models import CanonicalPost, ChannelTypeResolver, DedupePort, DirectMessage, EventPublisher


async def classify_direct_message(
    post: CanonicalPost,
    *,
    account_user_id: str,
    resolve_channel_type: ChannelTypeResolver,
) -> DirectMessage | None:
    """Fail closed unless this is an ordinary foreign post in a D channel."""

    if not account_user_id or post.sender_user_id == account_user_id or post.post_type != "":
        return None
    channel_type = post.channel_type
    if channel_type is None:
        try:
            channel_type = await resolve_channel_type(post.channel_id)
        except Exception:
            return None
    if channel_type != "D":
        return None
    return DirectMessage(
        post_id=post.post_id,
        channel_id=post.channel_id,
        sender_user_id=post.sender_user_id,
        message=post.message,
        created_at=post.created_at,
        sender_username=post.sender_username,
        root_id=post.root_id,
        file_ids=post.file_ids,
    )


class MessagePipeline:
    """Classify, durably mark, then publish a Time post."""

    def __init__(
        self,
        *,
        account_user_id: str,
        resolve_channel_type: ChannelTypeResolver,
        dedupe: DedupePort,
        publish: EventPublisher,
    ) -> None:
        self._account_user_id = account_user_id
        self._resolve_channel_type = resolve_channel_type
        self._dedupe = dedupe
        self._publish = publish

    async def async_process(self, post: CanonicalPost) -> bool:
        message = await classify_direct_message(
            post,
            account_user_id=self._account_user_id,
            resolve_channel_type=self._resolve_channel_type,
        )
        if message is None:
            return False
        try:
            is_new = await self._dedupe.async_check_and_mark(message.post_id)
        except Exception:
            return False
        if not is_new:
            return False
        await self._publish(message)
        return True
