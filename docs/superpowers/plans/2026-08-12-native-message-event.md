# Native Time Messenger Event Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make incoming Time Messenger direct messages selectable as a native Home Assistant event-entity trigger while retaining the existing raw event bus contract.

**Architecture:** Add one config-entry-backed `EventEntity` per Time Messenger account. The existing publisher will continue firing `time_messenger_event` and will also send the normalized payload over an entry-scoped HA dispatcher signal consumed by the event entity; the config-entry lifecycle loads the entity platform before starting the WebSocket runtime and unloads the platform before releasing runtime resources.

**Tech Stack:** Python 3.14, Home Assistant 2026.8.1 `EventEntity`, config entries, dispatcher helpers, pytest/pytest-asyncio, Ruff, mypy, HACS and hassfest validations.

## Global Constraints

- Keep Home Assistant support at exactly 2026.8.1 or newer for release 0.0.3.
- Preserve the public `time_messenger_event` name and schema-v1 payload unchanged.
- Keep message text redacted unless `include_message_text` is enabled in options.
- Use the stable `EventEntity` API; do not use legacy device automations or the experimental integration `trigger.py` API.
- Add no third-party runtime dependency.
- Publish release tag `v0.0.3` only after all local checks pass.

---

### Task 1: Native event entity and dual publisher

**Files:**
- Modify: `custom_components/time_messenger/const.py`
- Modify: `custom_components/time_messenger/event.py`
- Modify: `custom_components/time_messenger/translations/en.json`
- Modify: `custom_components/time_messenger/translations/ru.json`
- Modify: `tests/components/time_messenger/test_event.py`

**Interfaces:**
- Consumes: existing `event_data(message, *, config_entry_id, account_user_id, include_message_text) -> dict[str, object]`.
- Produces: `message_signal(config_entry_id: str) -> str`, `async_setup_entry(hass, entry, async_add_entities) -> None`, `TimeMessengerEventEntity`, and publisher delivery to both the event bus and dispatcher.

- [ ] **Step 1: Write failing entity and publisher tests**

Add tests that instantiate `TimeMessengerEventEntity(entry)`, assert stable unique ID, account service `DeviceInfo`, translation key, and `event_types == ["direct_message"]`. Add a callback-delivery test which patches `async_dispatcher_send`, calls `HomeAssistantEventPublisher.async_publish(message())`, and asserts both the unchanged `time_messenger_event` bus payload and one entry-scoped dispatcher payload.

```python
async def test_publisher_fires_bus_event_and_dispatches_native_entity_payload() -> None:
    with patch("custom_components.time_messenger.event.async_dispatcher_send") as dispatch:
        await publisher.async_publish(message())
    assert fired == [("time_messenger_event", expected_payload)]
    dispatch.assert_called_once_with(hass, message_signal("entry"), expected_payload)
```

- [ ] **Step 2: Run focused tests and confirm the new contract fails**

Run: `uv run pytest tests/components/time_messenger/test_event.py -q`

Expected: collection/import failure because `message_signal` and `TimeMessengerEventEntity` do not exist, or assertion failure because no dispatcher payload is sent.

- [ ] **Step 3: Add constants, event entity, and dispatcher delivery**

In `const.py`, add `EVENT_TYPE_DIRECT_MESSAGE = "direct_message"` and:

```python
def message_signal(config_entry_id: str) -> str:
    return f"{DOMAIN}_{config_entry_id}_message"
```

In `event.py`, keep `event_data` unchanged, add dispatcher delivery after the legacy bus fire, and implement the event platform entry point:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimeMessengerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TimeMessengerEventEntity(entry)])
```

Define `TimeMessengerEventEntity` with `_attr_has_entity_name = True`, `_attr_translation_key = "direct_message"`, `_attr_event_types = [EVENT_TYPE_DIRECT_MESSAGE]`, stable unique ID based on `entry.unique_id`, and a `DeviceInfo` service device owned by the config entry. Its `async_added_to_hass` registers an entry-scoped dispatcher callback through `self.async_on_remove`; that callback calls `_trigger_event(EVENT_TYPE_DIRECT_MESSAGE, data)` and `async_write_ha_state()`.

- [ ] **Step 4: Add English and Russian entity/event translations**

Add this structure under the top-level `entity` key in each translation file:

```json
{
  "event": {
    "direct_message": {
      "name": "Direct message",
      "state_attributes": {
        "event_type": {
          "state": {"direct_message": "Direct message received"}
        }
      }
    }
  }
}
```

Use Russian text `Личное сообщение` and `Получено личное сообщение` in `ru.json`.

- [ ] **Step 5: Run event and translation/package tests**

Run: `uv run pytest tests/components/time_messenger/test_event.py tests/components/time_messenger/test_packaging.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the independently working entity contract**

```bash
git add custom_components/time_messenger/const.py custom_components/time_messenger/event.py custom_components/time_messenger/translations/en.json custom_components/time_messenger/translations/ru.json tests/components/time_messenger/test_event.py
git commit -m "feat: expose direct messages as native events"
```

### Task 2: Config-entry platform lifecycle

**Files:**
- Modify: `custom_components/time_messenger/__init__.py`
- Modify: `tests/components/time_messenger/test_lifecycle.py`

**Interfaces:**
- Consumes: `TimeMessengerEventEntity` as the integration's `Platform.EVENT` platform and the existing `TimeMessengerRuntime` lifecycle.
- Produces: `PLATFORMS = [Platform.EVENT]`, platform setup before runtime start, and platform unload before runtime unload.

- [ ] **Step 1: Write failing setup and unload ordering tests**

Extend the lifecycle fakes with `hass.config_entries.async_forward_entry_setups` and `async_unload_platforms`. Assert setup forwards `[Platform.EVENT]` before `runtime.async_start`, and unload calls `async_unload_platforms` before `runtime.async_unload`. Assert a false platform-unload result does not discard the still-active runtime.

```python
assert calls == ["forward_event", "runtime_start"]
assert unload_calls == ["unload_event", "runtime_unload"]
```

- [ ] **Step 2: Run lifecycle tests and confirm failure**

Run: `uv run pytest tests/components/time_messenger/test_lifecycle.py -q`

Expected: FAIL because the integration does not forward or unload any entity platform.

- [ ] **Step 3: Implement standard platform setup/unload**

Import `Platform`, define `PLATFORMS = [Platform.EVENT]`, assign `entry.runtime_data`, await `hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)`, then start the runtime. On setup failure after runtime construction, unload the runtime-owned session before propagating. During unload, call `async_unload_platforms` first; only if it succeeds, call `entry.runtime_data.async_unload()` and return `True`.

- [ ] **Step 4: Run lifecycle, runtime, and event tests**

Run: `uv run pytest tests/components/time_messenger/test_lifecycle.py tests/components/time_messenger/test_runtime.py tests/components/time_messenger/test_event.py -q`

Expected: PASS.

- [ ] **Step 5: Commit lifecycle support**

```bash
git add custom_components/time_messenger/__init__.py tests/components/time_messenger/test_lifecycle.py
git commit -m "feat: load native message event platform"
```

### Task 3: User documentation and 0.0.3 release surfaces

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `custom_components/time_messenger/manifest.json`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `tests/components/time_messenger/test_documentation.py`
- Modify: `tests/components/time_messenger/test_packaging.py`

**Interfaces:**
- Consumes: native entity type `direct_message`, legacy event type `time_messenger_event`, and release version parity checker.
- Produces: UI-first Russian setup instructions and synchronized release version `0.0.3` on all release surfaces.

- [ ] **Step 1: Write failing documentation and version assertions**

Update documentation tests to require a native event-entity automation example or instructions containing `event_type: direct_message`, and update packaging constants to `RELEASE_VERSION = "0.0.3"` and `RELEASE_TAG = "v0.0.3"`.

- [ ] **Step 2: Run documentation/package/version tests and confirm failure**

Run: `uv run pytest tests/components/time_messenger/test_documentation.py tests/components/time_messenger/test_packaging.py tests/test_release_version.py -q`

Expected: FAIL because README and release surfaces still describe 0.0.2 and only the raw bus event.

- [ ] **Step 3: Rewrite README automation guidance around the UI**

Document: configure Time Messenger under Devices & services; create an automation; choose the `Direct message`/`Личное сообщение` event entity; select `Direct message received`/`Получено личное сообщение`; use trigger event data in actions. Retain a clearly labeled compatibility example for `time_messenger_event` so existing automations remain documented.

- [ ] **Step 4: Add changelog and synchronize release versions**

Add a top `## [0.0.3] - 2026-08-12` changelog entry. Set manifest and project versions to `0.0.3`, then run `uv lock` so the root package entry in `uv.lock` becomes `0.0.3` without changing the Home Assistant pin.

- [ ] **Step 5: Run documentation and version checks**

Run: `uv run pytest tests/components/time_messenger/test_documentation.py tests/components/time_messenger/test_packaging.py tests/test_release_version.py -q`

Run: `uv run python scripts/check_release_version.py --tag v0.0.3`

Expected: both commands PASS and report version parity `0.0.3`.

- [ ] **Step 6: Commit docs and release metadata**

```bash
git add README.md CHANGELOG.md custom_components/time_messenger/manifest.json pyproject.toml uv.lock tests/components/time_messenger/test_documentation.py tests/components/time_messenger/test_packaging.py
git commit -m "docs: prepare native event release 0.0.3"
```

### Task 4: Full verification and release publication

**Files:**
- Verify only: all tracked repository files

**Interfaces:**
- Consumes: completed implementation and existing tag-triggered release workflow.
- Produces: verified branch, annotated `v0.0.3` tag, pushed branch/tag, and GitHub Actions release run.

- [ ] **Step 1: Run formatting, lint, types, and all tests**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
```

Expected: every command exits 0.

- [ ] **Step 2: Run repository release gates**

Run: `uv run python scripts/check_release_version.py --tag v0.0.3`

If local HACS or hassfest commands are available, run the same validators used by `.github/workflows/hacs.yml` and `.github/workflows/hassfest.yml`; otherwise verify those reusable workflows and rely on the tag gate for their containerized checks.

- [ ] **Step 3: Inspect the exact release diff and clean status**

Run: `git diff --check HEAD~3..HEAD && git status --short && git log -4 --oneline`

Expected: no whitespace errors, no unexpected files, and the design/entity/lifecycle/release commits at the tip.

- [ ] **Step 4: Create and push release tag**

```bash
git tag -a v0.0.3 -m "Time Messenger 0.0.3"
git push origin codex/automated-releases
git push origin v0.0.3
```

Expected: both pushes succeed; the tag push starts `.github/workflows/release.yml`.

- [ ] **Step 5: Verify the GitHub release workflow**

Use `gh run list`/`gh run watch` for the tag-triggered Release workflow. Confirm runtime, HACS, hassfest, and Publish GitHub Release jobs all succeed, then confirm `gh release view v0.0.3` returns the published release.
