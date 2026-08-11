---
id: SPEC-syncer-time-messenger-t-bank-home-assist
companions:
  - authentication-methods.md
  - distribution-release.md
  - ../../planning-artifacts/architecture/architecture-syncer-ha-2026-08-11/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/research/technical-syncer-time-messenger-t-bank-home-assist-2026-08-11/research.md
sources: []
---

> **Канонический контракт.** Эта спецификация и все файлы из `companions:` обязательны для реализации, тестирования и валидации. Архитектурные решения AD-1–AD-13 из `ARCHITECTURE-SPINE.md` приняты без перенумерации.

# Личные сообщения Time Messenger в Home Assistant

## Why

Пользователю Home Assistant нужен единый сигнал о новых личных сообщениях Time и безопасный поддерживаемый способ получить интеграцию. HACS-дистрибуция, понятная документация и однозначные релизы превращают готовый код в устанавливаемый продукт без ручного копирования и догадок о совместимости.

## Capabilities

- **CAP-1**
  - **intent:** Пользователь может подключить собственную учётную запись Time к Home Assistant.
  - **success:** Каждый явно выбранный способ — OAuth, PAT или session — подтверждает identity через Time API и устанавливает авторизованный WebSocket; недействительные credentials запускают понятный reauth, а административно отключённый способ отображается как unsupported без утечки секрета.

- **CAP-2**
  - **intent:** Интеграция получает новые личные сообщения Time в реальном времени.
  - **success:** Событие Time `posted` для нового сообщения в 1:1 канале типа `D`, адресованного авторизованному пользователю, поступает в обработку через WebSocket без polling как штатного транспорта.

- **CAP-3**
  - **intent:** Интеграция пропускает только обычные личные сообщения от других пользователей.
  - **success:** Собственные сообщения, system/integration posts, неизвестные payload и каналы типов `G`, `P` или `O` не публикуют событие Home Assistant.

- **CAP-4**
  - **intent:** Интеграция подавляет повторную обработку одного сообщения.
  - **success:** После первой успешной публикации повторная доставка того же `post_id` не создаёт новое событие в течение 24 часов или пока ID входит в 5000 новейших записей, включая reconnect и restart Home Assistant.

- **CAP-5**
  - **intent:** Интеграция публикует документированное расширяемое событие Home Assistant с контекстом сообщения.
  - **success:** Автоматизации используют `time_messenger_event` со `schema_version: 1` и `type: direct_message`; обязательные и optional поля соответствуют AD-8, а текст доступен только после явного `include_message_text` opt-in.

- **CAP-6**
  - **intent:** Интеграция восстанавливает приём сообщений после временного разрыва связи.
  - **success:** Единственный per-entry WebSocket listener переподключается по политике AD-5, не оставляет zombie task после unload и не создаёт повторных событий для сохранённых `post_id`.

- **CAP-7**
  - **intent:** Пользователь может устанавливать и обновлять интеграцию через HACS.
  - **success:** HACS validation принимает repository как integration и устанавливает только `custom_components/time_messenger` в Home Assistant; установка из custom repository завершается без ручного копирования файлов.

- **CAP-8**
  - **intent:** Пользователь до установки получает достаточную документацию для безопасной настройки и эксплуатации.
  - **success:** HACS отображает repository README с назначением, совместимостью, установкой, OAuth/PAT/Session, настройкой, event schema, privacy, ограничениями, troubleshooting и удалением.

- **CAP-9**
  - **intent:** Maintainer выпускает однозначно идентифицируемые версии интеграции.
  - **success:** Первый release имеет версию `0.0.1`; `manifest.json`, `pyproject.toml`, `CHANGELOG.md` и GitHub Release согласованы, а автоматическая проверка отклоняет version drift.

- **CAP-10**
  - **intent:** Maintainer может доказать готовность repository к HACS-публикации до релиза.
  - **success:** Tests, lint, type check, HACS Action и Hassfest проходят без errors или ignores на pull request, push и release candidate.

## Constraints

- `ARCHITECTURE-SPINE.md` — adopted build contract: AD-1–AD-13 обязательны и не могут быть ослаблены реализацией нижнего уровня.
- Интеграционная поверхность — сервер Time Messenger; мобильный Syncer не задаёт API-контракт.
- Time API v4 изолирован adapter boundary; основной транспорт — авторизованный WebSocket, REST используется только для identity/capability checks и metadata recovery.
- Одна ConfigEntry изолирует одну пару tenant origin + персональная Time identity; несколько ConfigEntry разрешены без общего runtime или dedupe-state.
- Пользователь явно выбирает OAuth, PAT или session; fallback или downgrade между способами запрещён.
- Bearer передаётся только по проверенному HTTPS/WSS на bound tenant origin; redirects, cross-origin forwarding и `verify_ssl: false` запрещены.
- Listener принимает только `posted` с обычным `post.type`, channel type `D` и чужим `user_id`; неизвестные данные обрабатываются fail-closed.
- Dedupe-state сохраняется до публикации события. Это обеспечивает replay suppression, но не транзакционную exactly-once доставку через process crash, поскольку HA event bus не имеет acknowledgement.
- `message_text` имеет тип `string|null`, по умолчанию равен `null` и сопровождается `text_redacted: true`; raw text никогда не попадает в logs или diagnostics.
- V1 не гарантирует REST backfill или gap-free доставку после полного офлайна; возврат к backfill требует проверенной tenant cursor strategy.
- Target-tenant acceptance probe из AD-12 обязателен до заявления совместимости.
- Distribution и release выполняются по обязательному companion `distribution-release.md`; они не меняют runtime-инварианты AD-1–AD-13.
- Стартовая версия — `0.0.1`; существующие `0.1.0` в manifest и package metadata являются известным рассогласованием и заменяются синхронно.
- HACS repository содержит ровно одну integration directory `custom_components/time_messenger`; `content_in_root` и `zip_release` не используются.
- Public repository — `https://github.com/dancingpizza/time-messenger-home-assistant`; `documentation` указывает на его README, `issue_tracker` — на `/issues`, `codeowners` содержит `@dancingpizza`.
- Repository публикуется под MIT; brand для `0.0.1` — оригинальная нейтральная иконка без логотипов или товарных знаков Time/Т-Банка.
- README служит HACS landing page через `render_readme`; примеры event/automation используют только вымышленные или редактированные данные.
- Default-HACS readiness требует HACS Action, Hassfest и полноценный GitHub Release; одного tag недостаточно.
- Непроверенное использование логотипов или товарных знаков Time и Т-Банка запрещено.
- Network, storage, WebSocket processing и event publication не блокируют event loop Home Assistant.
- Интеграция публикует доменное событие и не содержит логики ламп, TTS или push-уведомлений.

## Non-goals

- Исходящие сообщения Home Assistant → Time.
- Slash-команды, outgoing/incoming webhooks, внешний broker или companion daemon.
- Group direct (`G`), private (`P`) и public (`O`) каналы в v1.
- Gap-free REST backfill в v1.
- EventEntity, device/sensor platforms и готовые device-specific автоматизации.
- Управление safety-critical устройствами и зависимость от внутренних механизмов мобильного Syncer.
- Заявка в default HACS catalog и upstream Home Assistant Brands в `0.0.1`; установка выполняется через URL custom repository.
- Автоматический push или GitHub Release без отдельного подтверждения после зелёных release gates.
- Изменение runtime/event/auth поведения ради упаковки HACS.

## Success signal

Пользователь добавляет публичный repository как HACS custom integration, устанавливает release `0.0.1`, проходит native config flow и получает ровно один `time_messenger_event` на новое чужое сообщение в 1:1 Time-чате. HACS/HA validation и runtime test suite зелёные, а документация позволяет настроить автоматизацию без чтения исходного кода.

## Assumptions

- `[ASSUMPTION]` Для v1 личным считается только канал Time типа `D`; расширение на `G` или `P` требует изменения scope.
- Target deployment соответствует проверенному baseline Home Assistant Core 2026.8.1 / Python 3.14.2+ и предоставляет доверенную цепочку TLS для Time.
- Для pre-1.0 релизов используется SemVer: GitHub tag `v0.0.1`, manifest/package version `0.0.1`.
- README имеет русскую основную документацию и краткое английское описание для HACS.

## Open Questions

- Какие OAuth client registration, scopes, PKCE и точный redirect URI разрешены целевым tenant?
- Как получать session token в SSO-only tenant, если `/api/v4/users/login` отключён; какой документированный endpoint заменяет его?
