---
id: SPEC-hacs-validation-ci
companions:
  - ../spec-syncer-time-messenger-t-bank-home-assist/SPEC.md
  - ../spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md
  - ../../planning-artifacts/architecture/architecture-syncer-ha-2026-08-11/ARCHITECTURE-SPINE.md
sources: []
---

> **Канонический контракт.** Эта SPEC и файлы из `companions:` задают полный контракт для автоматической проверки HACS release readiness.

# HACS validation и CI

## Why

Релиз нельзя считать готовым по локальному ручному осмотру: version drift, invalid HACS metadata или несовместимость с Home Assistant должны останавливать изменение до публикации. Этот срез делает release readiness воспроизводимой и проверяемой.

## Capabilities

- **CAP-10**
  - **intent:** Maintainer может автоматически доказать готовность repository к HACS release.
  - **success:** На pull request, push и release candidate проходят runtime tests, Ruff, format, mypy, version-parity, HACS Action и Hassfest без errors или скрытых ignores.

## Constraints

- Version-parity проверяет `manifest.json`, `pyproject.toml`, heading `CHANGELOG.md` и при release/tag контексте `v0.0.1`; `schema_version: 1` не участвует в package versioning.
- HACS Action запускается с category `integration`; Hassfest проверяет integration metadata, translations и config flow.
- Workflows используют pinned release tags или immutable references для third-party actions и минимально необходимые permissions.
- Existing local commands `pytest`, `ruff check`, `ruff format --check` и `mypy custom_components/time_messenger` остаются каноническими runtime gates.
- Live tenant probe и clean HACS install smoke фиксируются как внешние release gates, если требуют credentials или опубликованный GitHub Release; CI не имитирует успешный результат.
- CAP-1–CAP-9 и AD-1–AD-13 не меняются; push, tag и GitHub Release не выполняются без отдельного подтверждения.

## Non-goals

- Создание GitHub Release, branch protection или изменение repository settings.
- Default HACS submission и upstream Home Assistant Brands.
- Изменение runtime implementation ради прохождения packaging checks.

## Success signal

Локально выполняемые gates проходят, workflow definitions валидны, а намеренно внесённое расхождение версии приводит version-parity test к ожидаемому failure до публикации.
