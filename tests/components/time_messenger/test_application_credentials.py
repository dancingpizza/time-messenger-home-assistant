"""Tests for same-origin OAuth endpoint construction."""

from types import SimpleNamespace
from unittest.mock import patch

from custom_components.time_messenger.application_credentials import async_get_auth_implementation


async def test_oauth_endpoints_are_derived_from_auth_domain() -> None:
    credential = SimpleNamespace(client_id="client", client_secret="secret")
    with patch(
        "custom_components.time_messenger.application_credentials.config_entry_oauth2_flow.LocalOAuth2Implementation"
    ) as implementation:
        await async_get_auth_implementation(  # type: ignore[arg-type]
            SimpleNamespace(), "https://TIME.EXAMPLE/", credential
        )
    args = implementation.call_args.args
    assert args[-2:] == (
        "https://time.example/oauth/authorize",
        "https://time.example/oauth/access_token",
    )
