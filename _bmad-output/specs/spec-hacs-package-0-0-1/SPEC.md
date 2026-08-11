---
id: SPEC-hacs-package-0-0-1
companions:
  - ../spec-syncer-time-messenger-t-bank-home-assist/SPEC.md
  - ../spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md
  - ../../planning-artifacts/architecture/architecture-syncer-ha-2026-08-11/ARCHITECTURE-SPINE.md
sources: []
---

> **Канонический контракт.** Эта SPEC и файлы из `companions:` задают полный контракт для реализации, тестирования и проверки HACS-пакета версии `0.0.1`.

# HACS-пакет Time Messenger версии 0.0.1

## Why

Готовую Home Assistant integration невозможно безопасно устанавливать и обновлять через HACS, пока repository metadata, лицензия и версия расходятся или отсутствуют. Этот срез превращает существующий runtime в стандартный HACS custom repository package без изменения его поведения.

## Capabilities

- **CAP-7**
  - **intent:** Пользователь может установить и обновить integration из HACS custom repository без ручного выбора файлов.
  - **success:** HACS распознаёт repository как integration и устанавливает только `custom_components/time_messenger` стандартным directory-механизмом.

- **CAP-9**
  - **intent:** Maintainer может однозначно идентифицировать первый распространяемый release.
  - **success:** `manifest.json`, `pyproject.toml` и раздел `CHANGELOG.md` содержат `0.0.1`, а ожидаемый release tag определён как `v0.0.1`.

## Constraints

- Root `hacs.json` содержит `name: Time Messenger`, `render_readme: true` и `homeassistant: 2026.8.1`; `content_in_root`, `zip_release`, `filename` и `persistent_directory` запрещены.
- `manifest.json` содержит repository documentation URL, `/issues`, `codeowners: ["@dancingpizza"]`, текущие config-flow/dependency/integration metadata и версию `0.0.1`.
- Repository получает полный MIT License с copyright `2026 dancingpizza`; changelog описывает пользовательские изменения, ограничения и отсутствие migrations.
- Меняется только distribution metadata: CAP-1–CAP-6, AD-1–AD-13, runtime event schema и auth-поведение остаются неизменными.
- Push, tag и GitHub Release не выполняются без отдельного подтверждения пользователя.

## Non-goals

- README/HACS landing page, brand icon и CI workflows.
- Заявка в default HACS catalog, zip artifact или upstream Home Assistant Brands.
- Изменение runtime-кода, auth, WebSocket, filtering или dedupe.

## Success signal

Локальная metadata-проверка подтверждает standard HACS layout, MIT license и полное совпадение версии `0.0.1`; существующий runtime test suite остаётся зелёным.
