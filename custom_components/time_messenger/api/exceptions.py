"""Normalized Time adapter failures."""


class TimeMessengerError(Exception):
    """Base error without sensitive request/response data."""


class AuthError(TimeMessengerError):
    """Credentials are invalid or can no longer be refreshed."""


class TransientError(TimeMessengerError):
    """A retryable network or server failure."""


class RateLimitError(TransientError):
    """The tenant asked the client to delay a retry."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("Time API rate limit exceeded")
        self.retry_after = retry_after


class UnsupportedCapability(TimeMessengerError):
    """The selected capability is administratively unavailable."""


class ProtocolError(TimeMessengerError):
    """The server returned an invalid or unrecognized contract."""
