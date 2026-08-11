# Fresh-context verification — Time Messenger ↔ Home Assistant

Дата проверки: 2026-08-11  
Уровень: normal; spot-check только load-bearing claims  
Допустимые доказательства: официальная документация Time Messenger и Home Assistant

## Итог

Базовая двунаправленная интеграция **подтверждена**: Home Assistant может отправлять сообщения в Time через incoming webhook либо `POST /api/v4/posts`; Time может вызывать внешний HTTP endpoint через outgoing webhook или slash command; Home Assistant принимает такие вызовы webhook trigger. Для production custom integration связка `ConfigEntry` + `NotifyEntity` соответствует документированной модели Home Assistant.

Главная коррекция: утверждения, будто private/direct inbound требует polling и будто официальный WebSocket не найден, **опровергнуты**. Time официально документирует подключение ботов и пользователей к WebSocket с Bearer-токеном и получение событий в реальном времени. Поэтому рекомендуемый product-grade transport: **бот + REST для отправки + WebSocket для приёма**, а polling — резервный/backfill-механизм, не основной обязательный путь. При этом точный контракт доставки событий новых постов из private/direct каналов в просмотренных материалах не установлен и остаётся `unverified`.

## Проверенные утверждения

| Claim | Outcome | Проверка и коррекция |
| --- | --- | --- |
| HA→Time через incoming webhook | **verified** | Time разрешает incoming webhook URL для публичных и частных каналов; публикации помечаются как BOT. Доступность зависит от серверной настройки. [1] |
| HA→Time через `POST /api/v4/posts` с bot Bearer token | **verified** | Официальный Time cookbook показывает бот-токен в `Authorization: Bearer ...` и создание поста через v4 posts URL с полями `peer` и `message`. [2] |
| Time→HA через outgoing webhook; outgoing ограничен публичными каналами | **verified** | Документация прямо говорит: trigger words отправляют новые сообщения во внешние интеграции, а outgoing webhooks доступны только в публичных каналах. Это ограничение относится именно к outgoing webhook, не ко всем Time transports. [1] |
| Time→HA через slash command | **verified** | Time документирует slash commands как события во внешние интеграции, которые могут вернуть ответ в Time. Просмотренная страница не устанавливает channel-scope, поэтому работа slash command в private/direct чате — **unverified**. [1] |
| Private/DM inbound требует polling; официальный WebSocket отсутствует | **overturned** | Официальный cookbook говорит, что боты и пользователи могут подключаться к WebSocket с токеном и получать server events в реальном времени. Polling остаётся допустимым fallback/backfill, но не доказан как обязательный transport. Точная доставка `posted`/message events для private/direct каналов — **unverified** в рамках этого spot-check. [2] |
| PAT официально не рекомендуется для production | **verified** | Формулировка не является overclaim: официальная Time user guide прямо не рекомендует personal access tokens для production integrations и советует bots из-за инвалидации сессии при деактивации пользователя. Более узкий вывод: это рекомендация по типу credential, а не доказательство минимальных прав конкретного bot token. [3] |
| HA `rest_command` пригоден для MVP | **verified** | Поддерживаются POST, headers, templated payload, `content_type`, TLS verification и `response_variable`; официальный пример хранит authorization header через `!secret`. [4] |
| HA webhook trigger не имеет отдельной auth | **verified** | Endpoint `/api/webhook/<webhook_id>` не требует аутентификации кроме знания ID; ID следует считать паролем. По умолчанию webhook local-only, для прямого internet ingress нужен `local_only: false`; destructive/safety-critical actions документация запрещает. JSON доступен в `trigger.json`. [5] |
| `NotifyEntity` — подходящая outbound abstraction | **verified** | Notify entity stateless, предназначена в том числе для direct message/chat и предоставляет `async_send_message`. Это подтверждает HA-facing abstraction, но не само по себе конкретную retry/reauth реализацию. [6] |
| Bot token через config flow / `ConfigEntry.data` | **verified** | HA предупреждает, что connection data и API keys должны храниться в config entry `data`, а не в options простого schema flow. Это не доказывает шифрование at rest; исходный digest корректно оговаривает этот предел. [7] |

## Исправленная архитектурная рекомендация

1. **MVP фиксированного канала:** HA `rest_command` → Time incoming webhook либо `POST /api/v4/posts`; Time outgoing webhook/slash command → HA webhook trigger. Outgoing webhook подходит только публичному каналу.
2. **Product-grade custom integration:** отдельный bot identity; config flow с connection data в `ConfigEntry.data`; `NotifyEntity` для отправки; async REST `POST /api/v4/posts`; постоянный авторизованный Time WebSocket для inbound events.
3. **Polling:** использовать только как fallback, reconciliation/backfill или если WebSocket недоступен в конкретном deployment. До capability test не обещать private/DM event coverage.
4. **Безопасность:** случайный непредсказуемый HA `webhook_id`, `local_only` по возможности, allowlist команд и отсутствие safety-critical действий за unauthenticated webhook. Bot token/webhook URL не выводить в diagnostics и логах.
5. **Граница доказательства:** вывод относится к документированному Time Messenger. Эквивалентность конкретного Syncer deployment, его версия, лицензия, включённые integrations и WebSocket event permissions остаются **unverified**.

## Источники

1. Time Messenger / T-Bank — [Управление интеграциями](https://docs.time-messenger.ru/administration/settings/integrations/integration_management/), accessed 2026-08-11.
2. Time Messenger / T-Bank — [Приветствие пользователя при присоединении в канал: WebSocket + bot REST example](https://docs.time-messenger.ru/api/cookbook/websockets/), accessed 2026-08-11.
3. Time Messenger / ООО «ТЦР» — [Персональные токены доступа](https://time-messenger.ru/documentation/personal-access-tokens/), accessed 2026-08-11.
4. Home Assistant / Open Home Foundation — [RESTful Command](https://www.home-assistant.io/integrations/rest_command/), HA docs 2026.8.1, accessed 2026-08-11.
5. Home Assistant / Open Home Foundation — [Automation triggers: Webhook trigger](https://www.home-assistant.io/docs/automation/trigger/#webhook-trigger), HA docs 2026.8.1, accessed 2026-08-11.
6. Home Assistant Developer Docs / Open Home Foundation — [Notify entity](https://developers.home-assistant.io/docs/core/entity/notify/), updated 2026-03-24, accessed 2026-08-11.
7. Home Assistant Developer Docs / Open Home Foundation — [Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/), updated 2026-07-09, accessed 2026-08-11.
