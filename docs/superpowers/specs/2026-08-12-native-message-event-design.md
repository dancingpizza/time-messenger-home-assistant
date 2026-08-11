# Native Time Messenger Event Design

## Goal

Expose incoming Time Messenger direct messages through Home Assistant's native
automation UI without requiring users to type the raw
`time_messenger_event` event name.

## Decision

Add one Home Assistant `EventEntity` for each configured Time Messenger
account. The entity emits the custom event type `direct_message` whenever the
existing message pipeline accepts a new incoming direct message.

This follows Home Assistant's current recommendation to represent integration
events with event entities. A legacy device automation trigger is not suitable
for new integrations, and the new integration trigger API is explicitly marked
unstable in the Home Assistant developer documentation as of Home Assistant
2026.8.

## User Experience

After configuring Time Messenger, Home Assistant shows a Time Messenger account
device with a translated event entity named "Direct message". In the automation
editor the user selects that entity and its translated "Direct message received"
event instead of creating a raw event-bus trigger.

The event exposes the existing privacy-aware payload: account and sender IDs,
optional sender name, post and channel IDs, creation time, optional thread and
file IDs, and message text only when the user enabled message text in the
integration options.

## Architecture

- Forward the config entry to the `event` entity platform during setup and
  unload it through the standard config-entry platform lifecycle.
- Keep the network listener and filtering pipeline independent of Home
  Assistant entity internals.
- Extend the Home Assistant publisher so one accepted message is delivered both
  to the new event entity and to the existing event bus.
- Use an entry-scoped dispatcher signal to deliver the already-normalized event
  payload to the entity. Register and remove the entity callback through the
  entity lifecycle.
- Give the entity a stable unique ID derived from the config entry's immutable
  account identity, plus `DeviceInfo` for the Time Messenger account and tenant.
- Preserve `time_messenger_event` unchanged as a compatibility interface for
  existing automations.

## Failure and Lifecycle Behavior

An event received before entity-platform setup must not occur because the
platform is loaded before the listener starts. Entity unload removes its
dispatcher subscription before the runtime and network session are discarded.
Event-entity delivery is local and synchronous; it introduces no new network or
retry behavior. Existing authentication, reconnect, filtering, privacy, and
deduplication behavior remains unchanged.

## Localization and Documentation

Add complete English and Russian custom-integration translations for the entity
name and the `direct_message` event type. Update the README to lead with the
visual automation-editor flow, retain a legacy raw-event example, and explain
the privacy behavior. Add a `0.0.3` changelog entry.

## Verification

Tests cover entity registration, stable identity and device metadata, translated
event descriptors where supported by HA validation, event payload delivery,
privacy redaction, legacy bus compatibility, setup/unload ordering, and package
contents. Run the full Python test suite and the repository's release-version,
HACS, and hassfest-equivalent checks before tagging.

## Release

Bump the integration manifest to `0.0.3`, commit the implementation and release
documentation, create the annotated `v0.0.3` tag, and push the branch and tag.
The existing tag-triggered GitHub Actions workflow publishes the GitHub release
only after runtime, HACS, and hassfest jobs pass.
