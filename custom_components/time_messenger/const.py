"""Constants for Time Messenger."""

from typing import Final

from .schedule import WEEKDAYS

DOMAIN: Final = "time_messenger"
EVENT_TIME_MESSENGER: Final = "time_messenger_event"
EVENT_TYPE_DIRECT_MESSAGE: Final = "direct_message"
EVENT_SCHEMA_VERSION: Final = 1


def message_signal(config_entry_id: str) -> str:
    """Return the entry-scoped dispatcher signal for accepted messages."""

    return f"{DOMAIN}_{config_entry_id}_message"


def keep_online_issue_id(config_entry_id: str) -> str:
    """Return the entry-scoped Repairs issue for the optional online keeper."""

    return f"keep_online_unavailable_{config_entry_id}"


CONF_AUTH_MODE: Final = "auth_mode"
CONF_TENANT_ORIGIN: Final = "tenant_origin"
CONF_TOKEN: Final = "token"
CONF_USER_ID: Final = "user_id"
CONF_SERVER_VERSION: Final = "server_version"
CONF_INCLUDE_MESSAGE_TEXT: Final = "include_message_text"
CONF_KEEP_ONLINE: Final = "keep_online"
CONF_KEEP_ONLINE_WEEKDAYS: Final = "keep_online_weekdays"
CONF_KEEP_ONLINE_START_TIME: Final = "keep_online_start_time"
CONF_KEEP_ONLINE_END_TIME: Final = "keep_online_end_time"
CONF_KEEP_ONLINE_INTERVAL_MINUTES: Final = "keep_online_interval_minutes"

AUTH_MODE_OAUTH: Final = "oauth"
AUTH_MODE_PAT: Final = "pat"
AUTH_MODE_SESSION: Final = "session"
AUTH_MODES: Final = (AUTH_MODE_OAUTH, AUTH_MODE_PAT, AUTH_MODE_SESSION)

DEDUPE_TTL_SECONDS: Final = 24 * 60 * 60
DEDUPE_MAX_IDS: Final = 5_000
CHANNEL_CACHE_MAX_ENTRIES: Final = 512
AUTH_HEALTH_CHECK_INTERVAL: Final = 15 * 60.0
AUTH_HEALTH_CHECK_JITTER_RATIO: Final = 0.1
DEFAULT_KEEP_ONLINE: Final = False
KEEP_ONLINE_WEEKDAYS: Final = WEEKDAYS
DEFAULT_KEEP_ONLINE_WEEKDAYS: Final = ("mon", "tue", "wed", "thu", "fri")
DEFAULT_KEEP_ONLINE_START_TIME: Final = "09:00:00"
DEFAULT_KEEP_ONLINE_END_TIME: Final = "18:00:00"
DEFAULT_KEEP_ONLINE_INTERVAL_MINUTES: Final = 4
MIN_KEEP_ONLINE_INTERVAL_MINUTES: Final = 1
MAX_KEEP_ONLINE_INTERVAL_MINUTES: Final = 60
HEALTHY_CONNECTION_SECONDS: Final = 60.0
RECONNECT_CAPS: Final = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0)
REST_REQUEST_TIMEOUT: Final = 30.0
WS_CONNECT_TIMEOUT: Final = 30.0
WS_AUTH_TIMEOUT: Final = 20.0
WS_CLOSE_TIMEOUT: Final = 5.0
MAX_RETRY_DELAY: Final = 300.0
