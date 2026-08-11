"""Tenant-derived OAuth2 application credentials implementation."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .api.client import normalize_tenant_origin, origin_url


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Build authorization-code endpoints on the credential's bound tenant."""

    origin = normalize_tenant_origin(auth_domain)
    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass,
        origin,
        credential.client_id,
        credential.client_secret,
        origin_url(origin, "/oauth/authorize"),
        origin_url(origin, "/oauth/access_token"),
    )
