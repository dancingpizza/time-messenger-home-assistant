---
title: 'Документация и нейтральный branding для HACS'
type: 'feature'
created: '2026-08-11'
status: 'done'
review_loop_iteration: 0
baseline_commit: '56124286264b7d038b149bf6df2c6bcedd651a71'
context:
  - '_bmad-output/specs/spec-hacs-documentation-branding/SPEC.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-syncer-ha-2026-08-11/DESIGN.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-syncer-ha-2026-08-11/EXPERIENCE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** У HACS-пакета нет landing page и нейтрального brand asset, поэтому пользователь не может до установки быстро проверить совместимость, выбрать способ входа и скопировать безопасную automation.

**Approach:** Создать одностраничный русский README по adopted UX-spines, добавить оригинальную raster icon и закрепить CAP-8 контрактными тестами. Перед финализацией README выполнить Humanizer Gate: draft, still-AI audit, final.

## Boundaries & Constraints

**Always:** Сохранить факты SPEC и companions; использовать native GitHub/HACS Markdown с одним H1 и секциями H2/H3; показать пользу, ограничения v0.0.1, HACS и manual installation, OAuth/PAT/Session в принятом порядке, privacy, полный schema v1, три пользовательские YAML recipes, troubleshooting, removal и support. README должен прямо говорить, что integration неофициальная, а HACS-ссылка начнет устанавливать пакет только после push и GitHub Release. Иконка должна быть квадратным PNG без текста, логотипов и фирменных мотивов Time или Т-Банка. Финальный текст не содержит em/en dash и паттернов из Humanizer Gate.

**Ask First:** Любое изменение runtime, auth/event contracts, версии, repository metadata или выбранного юридически нейтрального направления иконки; любые push, tag, GitHub Release или внешняя публикация.

**Never:** Добавлять встроенные actions, `G/P/O`, backfill, gap-free обещания, automatic auth fallback, custom CSS/frontend, wide tables, сказочного героя, декоративные emoji, сторонние товарные знаки или изменять CAP-1–CAP-7, CAP-9–CAP-10 и AD-1–AD-13.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Быстрая оценка | Читатель открывает README | Сразу видит назначение, три use-case teaser, статус unofficial и совместимость | Несовместимая HA или непроверенный tenant останавливают рекомендацию установки |
| Установка | HACS доступен или недоступен | My link и UI path добавляют custom repository; recovery копирует только `custom_components/time_messenger` | Уточнить, что без опубликованного release remote install пока не завершится |
| Выбор auth | Tenant разрешает не все modes | OAuth рекомендован при организационной настройке, PAT описан как self-service, Session как fallback | Unsupported и reauth остаются в том же mode, browser emulation и downgrade запрещены |
| Первая automation | `message_text` по умолчанию `null` | Notification работает с metadata fallback; light/TTS требуют замены entity и подходящего устройства | TTS явно требует privacy opt-in для озвучивания текста; optional поля имеют fallback |
| Удаление | Пользователь удаляет ConfigEntry | Описано локальное удаление credentials/dedupe и best-effort Session logout | Remote revoke OAuth/PAT не обещается |

</frozen-after-approval>

## Code Map

- `README.md` -- отсутствующая HACS landing page; единственная пользовательская документация этого slice.
- `brand/icon.png` -- отсутствующий квадратный repository brand asset по SPEC; не описывать как гарантированно подхватываемый HACS Brands.
- `custom_components/time_messenger/event.py:event_data` -- канонический плоский payload и optional-поля schema v1.
- `custom_components/time_messenger/config_flow.py:TimeMessengerConfigFlow` -- точный порядок auth, same-mode reauth и privacy option; runtime-файл read-only.
- `custom_components/time_messenger/__init__.py:async_remove_entry` -- источник фактов об удалении, dedupe cleanup и Session logout; read-only.
- `custom_components/time_messenger/diagnostics.py:async_get_config_entry_diagnostics` -- allowlist без secrets/raw payload, но с идентификаторами, которые пользователь проверяет перед issue.
- `tests/components/time_messenger/test_event.py:test_message_text_is_redacted_by_default` -- golden redacted example с required и optional fields.
- `tests/components/time_messenger/test_documentation.py` -- новый CAP-8 contract: структура, факты, ссылки, schema, YAML и PNG.
- `tests/components/time_messenger/test_packaging.py` -- существующие CAP-7/9 package assertions; не расширять несвязанными CI-gates.

## Tasks & Acceptance

**Execution:**
- [x] `tests/components/time_messenger/test_documentation.py` -- сначала зафиксировать RED-проверки структуры README, schema drift, parseable recipes, Humanizer mechanical floor и валидного square PNG.
- [x] `README.md` -- написать factual draft по UX-порядку, сверить ссылки и code blocks, затем применить Humanizer Gate и сохранить только final.
- [x] `brand/icon.png` -- сгенерировать оригинальную нейтральную bitmap icon, удалить временный фон при необходимости и визуально проверить отсутствие текста/товарных знаков.
- [x] `_bmad-output/implementation-artifacts/spec-hacs-documentation-branding.md` -- записать verification evidence для draft, still-AI audit, final и пройденных проверок без публикации промежуточного текста.

**Acceptance Criteria:**
- Given пользователь открыл README в GitHub или HACS, when он читает страницу сверху вниз, then за один поток получает оценку, установку, auth choice, privacy/schema, recipes и восстановление без wide tables и технического талмуда.
- Given CAP-8 contract tests, when README или icon расходятся с schema v1, ссылками, UX-порядком либо нейтральным raster contract, then тест завершается ошибкой.
- Given финальный README, when выполнен Humanizer audit, then факты, URLs и code blocks сохранены, а AI-writing patterns и em/en dash отсутствуют.
- Given текущий локальный build, when работа завершена, then runtime, metadata и удаленный GitHub repository не изменены, push/tag/release не выполнены.

## Spec Change Log

## Design Notes

Первый recipe использует `persistent_notification.create`, чтобы запускаться без device-specific notify service. Light recipe честно зависит от поддержки `flash`; TTS использует пользовательские TTS и media player entities и не обещает встроенную поддержку Алисы. HACS My link: `https://my.home-assistant.io/redirect/hacs_repository/?owner=dancingpizza&repository=time-messenger-home-assistant&category=integration`.

## Verification

**Commands:**
- `uv run pytest -q` -- весь suite проходит без warnings/skips, скрывающих failures.
- `uv run ruff check . && uv run ruff format --check .` -- lint и format зелёные.
- `uv run mypy custom_components/time_messenger` -- runtime types не регрессировали.
- `git diff --check` -- нет whitespace errors.

**Manual checks:**
- Открыть `brand/icon.png` и проверить квадрат, прозрачность/фон, читаемость в малом размере, отсутствие текста и сторонней символики.
- Прочитать final README на desktop/mobile ширине и проверить heading hierarchy, alt text, короткий первый экран и понятные ограничения.

**Evidence (2026-08-11):**
- RED: `uv run pytest -q tests/components/time_messenger/test_documentation.py` завершился с `8 failed`; README и icon еще отсутствовали.
- Draft: factual README создан по adopted UX-порядку. JSON example сверен с `event_data`, три YAML block успешно разобраны PyYAML, HACS My link и issue URL проверены контрактным тестом.
- Still-AI audit: отмечены механический список из трех use cases, одинаковая анатомия auth-разделов и частые English technical terms. Три use cases и порядок auth сохранены как обязательный UX-контракт; формулировки сделаны предметными, а English оставлен только для точных терминов. Chatbot artifacts, рекламный язык, generic conclusion, механические bold lists, decorative emoji и em/en dash не обнаружены.
- Final: из draft, still-AI audit и final в repository сохранена только финальная версия `README.md`; mechanical Humanizer floor входит в CAP-8 test. Проверка документации: `8 passed`.
- Icon: built-in image generation, prompt `original neutral private-message to home-automation signal`; итоговый PNG уменьшен до `512x512`, RGB, визуально проверен в `64x64`. Текст, сторонние логотипы, товарные знаки и узнаваемые мотивы Time/Т-Банка отсутствуют. Asset не заявлен как автоматически подхватываемый HACS Brands.
- Review fixes: добавлены schema/type guards для recipes, проверка непустого TTS-текста, каноническое сравнение README schema с runtime `event_data`, CRC/IEND validation PNG, UX section order и расширенная emoji-проверка. README уточняет scope privacy opt-in, чувствительность metadata и отличие config-flow validation от acceptance probe.
- Step-04 patch review: уточнены замена example origin, формат tenant origin, настройка OAuth Application Credentials, multi-ConfigEntry filtering, граница log/diagnostics guarantee, semantics optional fields, privacy persistent notification, поведение неподдержанного light flash и ручное завершение Session. Contract assertions добавлены без ослабления прежних проверок.
- Post-review Humanizer re-audit: новые абзацы прочитаны как final, still-AI признаков не найдено; точные UI paths, code, URLs и security facts сохранены, em/en dash, chatbot artifacts, promotional language, title-case headings и decorative emoji отсутствуют.
- Полная проверка после review: `uv run pytest -q` завершился с `123 passed`; CAP-8 test отдельно завершился с `8 passed`; `uv run ruff check .`, `uv run ruff format --check .` и `uv run mypy custom_components/time_messenger` прошли.
- Whitespace: обычный `git diff --check` прошел для tracked diff; каждый новый text file отдельно проверен `git diff --no-index --check /dev/null <file>` без diagnostic output.
- Публикация не выполнялась: push, tag и GitHub Release отсутствуют; runtime и repository metadata не изменялись.

## Suggested Review Order

**Пользовательский путь**

- Введение быстро задает пользу, границы v0.0.1 и compatibility gate.
  [`README.md:1`](../../README.md#L1)

- Installation ведет через HACS и оставляет manual recovery без лишнего копирования.
  [`README.md:30`](../../README.md#L30)

**Авторизация и privacy**

- Auth hierarchy объясняет prerequisites, хранение credentials и same-mode reauth.
  [`README.md:43`](../../README.md#L43)

- Schema сохраняет privacy default и совпадает с production event contract.
  [`README.md:61`](../../README.md#L61)

**Automation и эксплуатация**

- Recipes остаются пользовательскими и учитывают multiple entries, devices и privacy.
  [`README.md:91`](../../README.md#L91)

- Troubleshooting и removal не обещают backfill или неподтвержденный remote revoke.
  [`README.md:169`](../../README.md#L169)

**Branding и проверки**

- Нейтральная raster icon показывает связь сообщения с домашней automation.
  [`icon.png:1`](../../brand/icon.png#L1)

- CAP-8 tests фиксируют UX-порядок, schema, recipes, Humanizer floor и PNG integrity.
  [`test_documentation.py:41`](../../tests/components/time_messenger/test_documentation.py#L41)
