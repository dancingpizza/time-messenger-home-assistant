# Current-technology review

Reviewed: 2026-08-11  
Artifact: `ARCHITECTURE-SPINE.md`  
Lens: current versions and primary-source support

## Verdict

**Needs targeted changes before build.** The pinned Home Assistant 2026.8 versions, Python, `aiohttp`, `ConfigEntry.runtime_data`, Time REST login/PAT/OAuth flows, WebSocket endpoint/authentication, and channel enum are current and supported. Two architectural rules do not yet implement what they claim (multi-tenant OAuth binding and system-post exclusion), while the event choice and broad HA compatibility range need explicit qualification.

## Findings

### High — Multi-tenant OAuth is not fully bound to Home Assistant Application Credentials

**Location:** AD-3, Structural Seed (`application_credentials.py`)

The spine says OAuth endpoints are tenant-derived, but the ordinary Home Assistant Application Credentials hook `async_get_authorization_server(hass)` returns one authorization server for the integration and receives no tenant/config-entry context. Home Assistant can support several credentials and per-credential implementations, but this requires the custom `async_get_auth_implementation(hass, auth_domain, credential)` path. Time credentials and callback URL are registered on a specific tenant, and its endpoints are tenant-relative `/oauth/authorize` and `/oauth/access_token`.

**Required change:** make the contract explicit: encode the normalized tenant origin in a stable `auth_domain`, create/import one Application Credential per `(tenant origin, client_id)`, and have `async_get_auth_implementation` validate/decode that origin and construct both URLs. Define the config-flow order so tenant and credential selection exist before OAuth starts. Without this, credentials for two Time tenants can be offered with the wrong authorization server.

Sources: [HA Application Credentials](https://developers.home-assistant.io/docs/core/platform/application_credentials/), [HA 2026.8.1 Application Credentials source](https://github.com/home-assistant/core/blob/2026.8.1/homeassistant/components/application_credentials/__init__.py), [Time OAuth2 Service Provider](https://docs.time-messenger.ru/integrations/oauth2_service_provider/).

### High — AD-6 does not actually exclude Time system posts

**Location:** AD-6

Filtering only `event == posted`, channel type `D`, and `post.user_id != account_user_id` does not satisfy AD-6's stated prevention of system posts. Time's current `Post` model includes a required `type` field; Time's data-format documentation states that a non-empty post type denotes a system-generated message. Such a post can still arrive as `posted` in a `D` channel and pass the existing sender test.

**Required change:** require an ordinary user-post predicate, minimally `post.type == ""`, before dedupe/publication (or define an explicit allowed-type set after tenant fixtures prove it). Add a tenant-probe fixture for a system post in a direct channel.

Sources: [Time posts-for-channel schema](https://docs.time-messenger.ru/api/v4/get-posts-for-channel/), [Time exported-data format](https://docs.time-messenger.ru/administration/data-managment/export-guide/data-format/).

### Medium — The public bus event is supported but conflicts with current HA guidance

**Location:** AD-8; Deferred — EventEntity

`hass.bus.async_fire("time_messenger_event", data)` and the `<domain>_event` name are supported. Current Home Assistant guidance nevertheless recommends event entities instead of direct bus events for discoverability. It also says events tied to a device or service should carry `device_id`, and event-only services should be registered in the device registry. The spine explicitly defers EventEntity and its event schema has no `device_id`.

**Required change:** either adopt an EventEntity/device-registry projection, or record direct bus publication as an intentional privacy trade-off (avoiding message text in entity state) and define how the Time account/service is attributed. Do not describe EventEntity as simply unnecessary without acknowledging the current recommendation.

Source: [Home Assistant — Firing events](https://developers.home-assistant.io/docs/integration_events/).

### Medium — The compatibility interval is broader than the verified dependency pins

**Location:** Stack

Home Assistant Core 2026.8.0 and 2026.8.1 both require Python `>=3.14.2` and pin `aiohttp==3.14.3`, so those values are correct. The declared HA interval `>=2026.8.0,<2027.0`, however, claims compatibility with unreleased/unverified monthly versions while simultaneously treating the inherited `aiohttp` pin as fixed.

**Required change:** state the verified baseline as Home Assistant `2026.8.1` (or tested `2026.8.x`), and describe Python/`aiohttp` as inherited from the selected HA release. Expand the supported HA range only through CI against each release; keeping `aiohttp` out of `manifest.json` is correct.

Sources: [HA Core 2026.8.0 pyproject](https://github.com/home-assistant/core/blob/2026.8.0/pyproject.toml), [HA Core 2026.8.1 pyproject](https://github.com/home-assistant/core/blob/2026.8.1/pyproject.toml).

## Verified current claims

| Claim | Result | Primary evidence |
| --- | --- | --- |
| HA 2026.8.1 uses Python `>=3.14.2` and `aiohttp==3.14.3` | Verified | [HA 2026.8.1 pyproject](https://github.com/home-assistant/core/blob/2026.8.1/pyproject.toml) |
| Typed `ConfigEntry.runtime_data` exists; `data`/`options` are not mutated directly | Verified | [HA 2026.8.1 `config_entries.py`](https://github.com/home-assistant/core/blob/2026.8.1/homeassistant/config_entries.py) |
| HA-managed OAuth2 session refreshes and writes refreshed token through `async_update_entry` | Verified | [HA 2026.8.1 OAuth2 flow source](https://github.com/home-assistant/core/blob/2026.8.1/homeassistant/helpers/config_entry_oauth2_flow.py) |
| Time session login accepts `login_id`, password, optional MFA `token`; response token is in `Token` header and used as Bearer | Verified | [Time authentication](https://docs.time-messenger.ru/api/v4/%D0%B0%D1%83%D1%82%D0%B5%D0%BD%D1%82%D0%B8%D1%84%D0%B8%D0%BA%D0%B0%D1%86%D0%B8%D1%8F/) |
| Time PAT uses Bearer and remains valid until revocation | Verified | [Time authentication](https://docs.time-messenger.ru/api/v4/%D0%B0%D1%83%D1%82%D0%B5%D0%BD%D1%82%D0%B8%D1%84%D0%B8%D0%BA%D0%B0%D1%86%D0%B8%D1%8F/) |
| Time OAuth supports authorization code plus refresh, and also documents implicit grant | Verified; prohibiting implicit is a sound architecture choice | [Time OAuth2 Service Provider](https://docs.time-messenger.ru/integrations/oauth2_service_provider/) |
| Time WebSocket is `/api/v4/websocket`, accepts Authorization/cookie or authentication challenge, then emits `hello` with server version | Verified | [Time WebSocket](https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/) |
| Channel enum contains `P`, `O`, `G`, `D`; direct-channel endpoint creates a two-user DM | Verified | [Time channel schema](https://docs.time-messenger.ru/api/v4/get-channels-for-user/), [Time direct channel](https://docs.time-messenger.ru/api/v4/create-direct-channel/) |
| Public docs guarantee `posted` delivery for all required private/direct tenant cases | **Not verified**; AD-12 correctly keeps this behind a tenant acceptance gate | [Time WebSocket](https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/), [Time WebSocket cookbook](https://docs.time-messenger.ru/api/cookbook/websockets/) |

