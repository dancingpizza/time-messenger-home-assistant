---
id: SPEC-syncer-time-messenger-t-bank-home-assist
companions:
  - authentication-methods.md
  - ../../planning-artifacts/architecture/architecture-syncer-ha-2026-08-11/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/research/technical-syncer-time-messenger-t-bank-home-assist-2026-08-11/research.md
sources: []
---

> **Канонический контракт.** Эта спецификация и все файлы из `companions:` обязательны для реализации, тестирования и валидации. Архитектурные решения AD-1–AD-13 из `ARCHITECTURE-SPINE.md` приняты без перенумерации.

# Личные сообщения Time Messenger в Home Assistant

## Why

Пользователю Home Assistant нужен единый сигнал о новых личных сообщениях Time, чтобы запускать произвольные автоматизации — свет, TTS, push-уведомления и будущие сценарии — без изменения интеграции для каждого действия.

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
- Network, storage, WebSocket processing и event publication не блокируют event loop Home Assistant.
- Интеграция публикует доменное событие и не содержит логики ламп, TTS или push-уведомлений.

## Non-goals

- Исходящие сообщения Home Assistant → Time.
- Slash-команды, outgoing/incoming webhooks, внешний broker или companion daemon.
- Group direct (`G`), private (`P`) и public (`O`) каналы в v1.
- Gap-free REST backfill в v1.
- EventEntity, device/sensor platforms и готовые device-specific автоматизации.
- Управление safety-critical устройствами и зависимость от внутренних механизмов мобильного Syncer.

## Success signal

Сообщение из другого аккаунта в 1:1 Time-чат создаёт ровно один `time_messenger_event` с корректными identity, channel и post IDs; текст появляется только при opt-in. Собственное, повторное, системное, групповое или публичное сообщение события не создаёт. После разрыва listener восстанавливается, а новая автоматизация света, TTS или уведомления подключается только средствами Home Assistant.

## Assumptions

- `[ASSUMPTION]` Для v1 личным считается только канал Time типа `D`; расширение на `G` или `P` требует изменения scope.
- Target deployment соответствует проверенному baseline Home Assistant Core 2026.8.1 / Python 3.14.2+ и предоставляет доверенную цепочку TLS для Time.

## Open Questions

- Какие OAuth client registration, scopes, PKCE и точный redirect URI разрешены целевым tenant?
- Как получать session token в SSO-only tenant, если `/api/v4/users/login` отключён; какой документированный endpoint заменяет его?
