"""Constants for Time Messenger."""

from typing import Final

DOMAIN: Final = "time_messenger"
EVENT_TIME_MESSENGER: Final = "time_messenger_event"
EVENT_TYPE_DIRECT_MESSAGE: Final = "direct_message"
EVENT_SCHEMA_VERSION: Final = 1


def message_signal(config_entry_id: str) -> str:
    """Return the entry-scoped dispatcher signal for accepted messages."""

    return f"{DOMAIN}_{config_entry_id}_message"


CONF_AUTH_MODE: Final = "auth_mode"
CONF_TENANT_ORIGIN: Final = "tenant_origin"
CONF_TOKEN: Final = "token"
CONF_USER_ID: Final = "user_id"
CONF_SERVER_VERSION: Final = "server_version"
CONF_INCLUDE_MESSAGE_TEXT: Final = "include_message_text"

AUTH_MODE_OAUTH: Final = "oauth"
AUTH_MODE_PAT: Final = "pat"
AUTH_MODE_SESSION: Final = "session"
AUTH_MODES: Final = (AUTH_MODE_OAUTH, AUTH_MODE_PAT, AUTH_MODE_SESSION)

DEDUPE_TTL_SECONDS: Final = 24 * 60 * 60
DEDUPE_MAX_IDS: Final = 5_000
CHANNEL_CACHE_MAX_ENTRIES: Final = 512
HEALTHY_CONNECTION_SECONDS: Final = 60.0
RECONNECT_CAPS: Final = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0)
REST_REQUEST_TIMEOUT: Final = 30.0
WS_CONNECT_TIMEOUT: Final = 30.0
WS_AUTH_TIMEOUT: Final = 20.0
WS_CLOSE_TIMEOUT: Final = 5.0
MAX_RETRY_DELAY: Final = 300.0
