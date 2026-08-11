# HACS distribution, документация и release contract

Этот companion определяет CAP-7–CAP-10. Runtime-код и AD-1–AD-13 не меняются.

## Repository contract

| Поверхность | Обязательный результат |
| --- | --- |
| `custom_components/time_messenger/` | Единственная integration directory; все runtime-файлы и `manifest.json` находятся внутри неё. |
| `hacs.json` | Root-файл с `name: Time Messenger`, `render_readme: true`, `homeassistant: 2026.8.1`; без `content_in_root`, `zip_release`, `filename`, `persistent_directory` и неподтверждённого `country`. |
| `manifest.json` | `domain`, `name`, `version: 0.0.1`, `documentation: https://github.com/dancingpizza/time-messenger-home-assistant`, `issue_tracker: https://github.com/dancingpizza/time-messenger-home-assistant/issues`, `codeowners: ["@dancingpizza"]`, config flow, dependencies, integration type и IoT class. |
| `README.md` | HACS landing page и основная пользовательская документация. |
| `CHANGELOG.md` | Раздел `0.0.1` с пользовательскими изменениями, ограничениями и migration notes; пустые или generated commit dumps запрещены. |
| `LICENSE` | Полный текст MIT License с корректным copyright holder/year. |
| `brand/icon.png` | Новая сгенерированная нейтральная HACS-compatible иконка без логотипов или товарных знаков Time/Т-Банка. |
| `.github/workflows/` | CI, HACS validation, Hassfest и version-parity gate. |

Официальные основания: [HACS general publishing requirements](https://www.hacs.dev/docs/publish/start/), [HACS integration requirements](https://www.hacs.dev/docs/publish/integration/), [default repository checklist](https://www.hacs.dev/docs/publish/include/), [Home Assistant manifest contract](https://developers.home-assistant.io/docs/creating_integration_manifest/).

## HACS page and README contract

README содержит в таком порядке:

1. Название, краткое русское описание и короткий English summary; явное указание, что проект является неофициальной Home Assistant integration.
2. Возможности и ограничения v0.0.1: только чужие обычные сообщения в 1:1 `D`, без `G/P/O`, backfill и встроенных automation actions.
3. Совместимость: Home Assistant `2026.8.1+`, Python предоставляется Home Assistant, Time API v4 и обязательный tenant acceptance probe.
4. Установка через HACS custom repository `dancingpizza/time-messenger-home-assistant`, HACS My link, перезапуск Home Assistant и добавление integration через Settings → Devices & services.
5. Manual install как recovery path: копируется только `custom_components/time_messenger`.
6. Настройка OAuth, PAT и Session с предупреждениями о tenant policy, MFA и невозможности browser-login emulation.
7. Privacy: `message_text` скрыт по умолчанию, secrets и raw payload не попадают в diagnostics/logs.
8. Полный `time_messenger_event` schema v1 и redacted example.
9. Минимальные YAML automation examples для уведомления, мигания света и TTS; примеры являются пользовательскими recipes, не встроенной логикой integration.
10. Reauth, reconnect, diagnostics, troubleshooting, known limitations, removal и support/issue links.

README не обещает gap-free delivery, поддержку любого tenant или все три auth mode на административно ограниченном сервере.

## Versioning and release invariants

- SemVer применяется до `1.0.0`; первый release — `0.0.1`, GitHub tag — `v0.0.1`.
- `custom_components/time_messenger/manifest.json` и `pyproject.toml` содержат `0.0.1`; heading changelog и release tag описывают ту же версию.
- CI извлекает эти значения и завершается ошибкой при несовпадении, invalid AwesomeVersion/SemVer или отсутствии changelog entry.
- Версия меняется отдельным release change; runtime `schema_version: 1` не связан с package version и не повышается без breaking event change.
- GitHub Release создаётся только из прошедшего CI commit и содержит release notes. Простой tag не считается релизом HACS.
- Release artifact использует стандартную HACS directory installation; zip packaging не добавляется в `0.0.1`.

## Validation gates

| Gate | Условие успеха |
| --- | --- |
| Runtime | Существующие pytest, Ruff, format и mypy проходят без warnings/skips, скрывающих failures. |
| Metadata | JSON валиден; manifest, HACS metadata, version parity, documentation/issue URLs и codeowner проверены. |
| HACS | `hacs/action` с category `integration` проходит без errors или ignores на PR/push и проверяет release candidate. |
| Home Assistant | Hassfest проходит для custom integration metadata/translations/config flow. |
| Install smoke | Чистый HA `2026.8.1` устанавливает integration из HACS custom repository, импортирует component и открывает config flow. |
| Tenant | AD-12 probe пройден отдельно; HACS validation не заменяет проверку реального Time tenant. |
| Release | Public GitHub Release `v0.0.1` видим HACS как remote version и устанавливается/обновляется без лишних repository-файлов. |

## External repository settings

До HACS publication владелец repository вручную задаёт:

- public visibility, issues enabled и короткое repository description;
- GitHub topics как минимум `home-assistant`, `hacs`, `custom-integration`, `time-messenger`;
- branch protection, требующий CI/HACS/Hassfest checks;
- release permissions для maintainer `@dancingpizza`;
- HACS My link для `dancingpizza/time-messenger-home-assistant`.

Default HACS submission и upstream Home Assistant Brands не входят в `0.0.1`: custom repository устанавливается напрямую по URL без заявки. Возможная заявка становится отдельной будущей работой после успешного release.
