# Спека: HACS-упаковка, релизы и CI-валидация

Статус: реализовано (`0.0.1`). Дополняет
[спеку интеграции](2026-08-11-time-messenger-integration.md); runtime-код и
[архитектурные решения](../architecture.md) этот документ не меняет.

## Зачем

Готовую Home Assistant integration невозможно безопасно устанавливать и
обновлять через HACS, пока repository metadata, лицензия и версия
расходятся или отсутствуют. Релиз нельзя считать готовым по ручному
осмотру — version drift, invalid HACS metadata или несовместимость с Home
Assistant должны останавливать изменение до публикации.

## Repository contract

| Поверхность | Обязательный результат |
| --- | --- |
| `custom_components/time_messenger/` | Единственная integration directory; все runtime-файлы и `manifest.json` внутри неё. |
| `hacs.json` | Root-файл с `name`, `render_readme: true`, `homeassistant`; без `content_in_root`, `zip_release`, `filename`, `persistent_directory`. |
| `manifest.json` | `domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners`, config flow, dependencies, integration type, IoT class. |
| `README.md` | HACS landing page и основная пользовательская документация; голос и структура — по [style-guide.md](../style-guide.md). |
| `CHANGELOG.md` | Раздел на каждую версию с пользовательскими изменениями и ограничениями; пустые или generated commit dumps запрещены. |
| `LICENSE` | Полный текст MIT License с корректным copyright holder/year. |
| `custom_components/time_messenger/brand/icon.png` | HACS-compatible квадратная PNG-иконка. ⚠️ Требование «без товарных знаков Time/Т-Банка» отменено начиная с `0.0.5` — см. [2026-08-13-brand-icon-refresh.md](2026-08-13-brand-icon-refresh.md). |
| `.github/workflows/` | CI, HACS validation, Hassfest и version-parity gate. |

Официальные основания: [HACS general publishing requirements](https://www.hacs.dev/docs/publish/start/),
[HACS integration requirements](https://www.hacs.dev/docs/publish/integration/),
[Home Assistant manifest contract](https://developers.home-assistant.io/docs/creating_integration_manifest/).

## Версионирование и релизы

- SemVer до `1.0.0`.
- `custom_components/time_messenger/manifest.json` и `pyproject.toml`
  содержат одну и ту же версию; heading `CHANGELOG.md` и GitHub Release tag
  описывают ту же версию (`scripts/check_release_version.py` проверяет это).
- Runtime `schema_version` события `time_messenger_event` не связан с
  package version и не повышается без breaking event change.
- GitHub Release создаётся только из прошедшего CI commit; простой tag не
  считается релизом HACS.
- Устанавливается стандартным HACS directory installation; zip packaging не
  используется.

## Validation gates

| Gate | Условие успеха |
| --- | --- |
| Runtime | `pytest`, `ruff check`, `ruff format --check`, `mypy` проходят без warnings/skips, скрывающих failures. |
| Metadata | manifest, HACS metadata, version parity, documentation/issue URLs и codeowner проверены. |
| HACS | `hacs/action` с category `integration` проходит без errors или ignores на PR/push и проверяет release candidate. |
| Home Assistant | Hassfest проходит для custom integration metadata/translations/config flow. |
| Install smoke | Чистый Home Assistant устанавливает integration из HACS custom repository, импортирует component и открывает config flow. |
| Tenant | AD-12 probe (`scripts/probe_time_tenant.py`) пройден отдельно на реальном Time tenant; HACS validation его не заменяет. |
| Release | Public GitHub Release видим HACS как remote version и устанавливается/обновляется без лишних repository-файлов. |

Workflows используют pinned release tags или immutable references для
third-party actions и минимально необходимые permissions. Live tenant probe
и clean HACS install smoke — внешние release gates, если требуют
credentials или опубликованный GitHub Release; CI не имитирует успешный
результат.

## Non-goals

- Заявка в default HACS catalog или upstream Home Assistant Brands —
  устанавливается через URL custom repository.
- Автоматический push или GitHub Release без отдельного подтверждения после
  зелёных gates.
- Изменение runtime/event/auth поведения ради упаковки HACS.

## Внешние настройки репозитория

Вне кода, вручную у владельца repository: public visibility, issues
enabled, короткое description; GitHub topics (`home-assistant`, `hacs`,
`custom-integration`, `time-messenger`); branch protection, требующий
CI/HACS/Hassfest checks; release permissions для codeowner.
