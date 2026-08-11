# Раунд 1 — архитектура интеграции Syncer / Time Messenger с Home Assistant

Дата исследования: 2026-08-11  
Направление: архитектура и реализация  
Метод: только открытая документация, полученная в этом раунде; проектные файлы не использовались как доказательства.  
Охват: 8 реально прочитанных официальных источников (4 Time Messenger, 4 Home Assistant).

## Краткий вывод

Для **документированного Time Messenger** двунаправленная интеграция технически реализуема. Минимальный безопасный вариант: фиксированный канал Time через входящий webhook для HA→Time и исходящий webhook Time→HA, направленный на недеструктивную HA automation с длинным случайным `webhook_id`. Если нужны личные сообщения, несколько каналов, нормальная UI-настройка и обработка ошибок, нужен custom integration: `NotifyEntity` + async вызов `POST /api/v4/posts` с токеном отдельного бота.

Для продукта под именем **Syncer** вывод пока условный: в прочитанной официальной документации не найдено подтверждение, что конкретный корпоративный инстанс Syncer предоставляет тот же Time API v4 и те же webhook-настройки. До проверки URL/версии/лицензии сервера нельзя считать интеграцию с Syncer доказанной.

## Claims

### C1. Time позволяет внешней системе публиковать сообщения через входящие webhooks; они могут быть разрешены для публичных и частных каналов

- claim: На стороне Time существует документированная поверхность для простого HA→Time без пользовательского API-токена: администратор может разрешить входящие webhooks, а создаваемые webhook URL предназначены для публичных и частных каналов. Сообщения помечаются как бот-сообщения.
- URL: https://docs.time-messenger.ru/administration/settings/integrations/integration_management/
- publisher: Time Messenger / T-Bank
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high
- class: integration

### C2. Time→внешняя система поддерживается исходящими webhooks, но только из публичных каналов

- claim: Time документирует исходящие webhooks с триггерными словами, отправляющие новые сообщения во внешнюю интеграцию; по соображениям безопасности они доступны только в публичных каналах. Это исключает данный путь для личных и частных чатов.
- URL: https://docs.time-messenger.ru/administration/settings/integrations/integration_management/
- publisher: Time Messenger / T-Bank
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high
- class: integration

### C3. HA→Time через API v4 документирован как один POST с Bearer-токеном бота

- claim: Time cookbook документирует `POST https://<API_URL>/api/v4/posts` с `Authorization: Bearer <bot token>` и JSON; пример отправляет `message` адресату через поле `peer`. Это достаточная поверхность для notify entity или REST-команды.
- URL: https://docs.time-messenger.ru/api/cookbook/send-a-message/
- publisher: Time Messenger / T-Bank
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high
- class: integration

### C4. Персональный токен пользователя не является рекомендуемым production credential

- claim: Официальное руководство Time прямо не рекомендует personal access token для production-интеграций и советует ботов; сессия PAT отключается при деактивации пользователя. Следовательно, отдельный бот с минимальными правами предпочтительнее пользовательского/администраторского PAT.
- URL: https://time-messenger.ru/documentation/personal-access-tokens/
- publisher: Time Messenger / ООО «ТЦР»
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high
- class: security

### C5. Polling частных/личных каналов возможен, но требует курсора, дедупликации и восстановления разрывов

- claim: `GET /api/v4/channels/:channel_id/posts` поддерживает `since` в Unix ms и требует `read_channel`; результат ограничен 1000 изменёнными постами, а последовательность не гарантируется. Поэтому polling — документированный fallback, но клиент обязан хранить водяной знак/ID, дедуплицировать и уметь восполнять пропуски.
- URL: https://docs.time-messenger.ru/api/v4/get-posts-for-channel/
- publisher: Time Messenger / T-Bank
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high
- class: architecture

### C6. Нативная HA-абстракция для исходящих сообщений — notify entity

- claim: Home Assistant определяет `NotifyEntity` как stateless entity для отправки, в том числе direct message/chat, и предоставляет `async_send_message(message, title)`. Поэтому продуктовый custom integration должен экспонировать `notify.<target>` и реализовать неблокирующий сетевой вызов Time API.
- URL: https://developers.home-assistant.io/docs/core/entity/notify/
- publisher: Home Assistant Developer Docs / Open Home Foundation
- pub_date: 2026-03-24 (last updated)
- accessed: 2026-08-11
- confidence: high
- class: architecture

### C7. HA webhook trigger не имеет отдельной аутентификации: секретом является сам webhook ID

- claim: HA принимает webhook на `/api/webhook/<webhook_id>`; кроме знания ID аутентификация не требуется. По умолчанию endpoint локальный, для прямого доступа из интернета нужен `local_only: false`; документация требует уникальный непредсказуемый ID и запрещает использовать такой вход для опасных действий. JSON доступен как `trigger.json`.
- URL: https://www.home-assistant.io/docs/automation/trigger/#webhook-trigger
- publisher: Home Assistant / Open Home Foundation
- pub_date: n.d. (страница документации Home Assistant 2026.8.1)
- accessed: 2026-08-11
- confidence: high
- class: security

### C8. `rest_command` годится для MVP HA→Time и поддерживает секретный Authorization header

- claim: Home Assistant `rest_command` создаёт вызываемые из automation действия, поддерживает POST, headers, JSON payload, TLS verification и `authorization: !secret ...`; ответ доступен через `response_variable`. Это документированный low-code путь к Time `/api/v4/posts`, но он не даёт полноценной сущности/reauth UX.
- URL: https://www.home-assistant.io/integrations/rest_command/
- publisher: Home Assistant / Open Home Foundation
- pub_date: n.d. (страница документации Home Assistant 2026.8.1)
- accessed: 2026-08-11
- confidence: high
- class: integration

### C9. Версионная граница доказательства — Time API v4 и HA 2026.8.1

- claim: Проверенные Time endpoints находятся под `/api/v4`; проверенная пользовательская документация HA отображает версию 2026.8.1. Совместимость с Time API v5, иными/старыми сборками Time либо ребрендированным Syncer в этом раунде не доказана.
- URL: https://docs.time-messenger.ru/api/cookbook/send-a-message/ ; https://www.home-assistant.io/docs/automation/trigger/
- publisher: Time Messenger / T-Bank; Home Assistant / Open Home Foundation
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high для проверенной границы; low для любой экстраполяции за неё
- class: version-compatibility

### C10. Production credential custom integration следует принимать через config flow и хранить как connection data

- claim: Home Assistant config flow управляет созданием config entry; документация отдельно указывает, что API keys и иные данные соединения должны храниться в `ConfigEntry.data`, а не в options простого schema flow. Это подходящий HA-механизм для bot token; он не доказывает шифрование токена at rest.
- URL: https://developers.home-assistant.io/docs/core/integration/config_flow/
- publisher: Home Assistant Developer Docs / Open Home Foundation
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high
- class: security

## feasible_paths

### Path A — минимальный двунаправленный bridge, фиксированный публичный канал

1. **HA→Time:** создать scoped incoming webhook одного канала Time (C1); вызывать его из HA `rest_command`, секрет URL/токен держать через `!secret`, оставить `verify_ssl: true` (C8).
2. **Time→HA:** создать outgoing webhook на публичном канале с узким trigger word и callback на `https://<ha>/api/webhook/<random-id>` (C2, C7).
3. **HA policy:** принимать только POST/PUT, проверять ожидаемую структуру и allowlist команд; запускать только недеструктивные сценарии. Для замков, ворот, сигнализации, отключения защит и иных safety-critical действий webhook не использовать (C7).
4. **Сетевой профиль:** предпочтительно private routing/VPN или HA Cloud webhook; `local_only: false` включать лишь когда Time физически не может достичь локального HA endpoint (C7).

Оценка: **feasible для Time**, low implementation cost. Ограничение: входящий поток только из публичного канала (C2).

### Path B — product-grade custom integration

1. Config flow: `base_url`, bot token, default peer/channel; connection credentials — в `ConfigEntry.data` (C10).
2. Notify platform: одна или несколько `NotifyEntity`, `async_send_message` вызывает `POST /api/v4/posts` (C3, C6).
3. Inbound push: outgoing Time webhook → отдельный handler/HA webhook; валидировать тип сообщения, target и allowlist, вести дедупликацию.
4. Inbound private/DM fallback: периодический `GET .../posts?since=...`; сохранять durable cursor и обработанные post IDs, делать backfill при разрывах (C5).
5. Обработка ошибок: 401/403 → reauth/repair, 429/5xx → bounded exponential backoff; токены не логировать. Эти политики — **условная инженерная рекомендация**, а не найденный контракт Time по rate limits.

Оценка: **feasible для Time после проверки прав бота и маршрута сети**; medium implementation cost.

### Path C — только исходящие уведомления, YAML MVP

- `rest_command` → Time `/api/v4/posts` с bot Bearer token из `!secret` (C3, C8).
- Подходит для быстрого прототипа и шаблонных automation; не даёт discoverable notify entity, UI reauth и общей очереди/дедупликации.

Оценка: **feasible**, самый быстрый путь проверить серверный URL, сертификат, права и payload до разработки custom integration.

## Минимальный безопасный дизайн

- Отдельный bot identity, не PAT человека и тем более не admin PAT (C4).
- Least privilege: один нужный канал/peer; не включать `messages:all` без необходимости.
- Секреты: YAML MVP — `!secret` в `rest_command` (C8); custom integration — connection data в config entry (C10). Не показывать token/webhook ID в diagnostics, trace payload и логах.
- TLS certificate verification включена; публичный HA endpoint не открывать без необходимости.
- Для Time→HA считать случайный webhook ID credential (C7); ротировать при утечке.
- Входящие команды разделить на read-only/low-risk и privileged. Последние требуют второго доверенного канала или human confirmation; прямой webhook trigger не должен выполнять safety-critical action (C7).
- Идемпотентность: дедупликация по post ID/event ID; собственный source marker нужен для подавления циклов HA→Time→HA. Наличие подходящего marker в payload Time должно быть проверено на реальном сервере; сейчас это условная рекомендация.
- Polling: хранить cursor и dedupe state durable, ограничивать частоту, backfill пропуски из-за documented non-sequential `since` (C5).

## blockers

1. **Syncer≠Time не доказано.** Нет найденной официальной связки «Syncer использует Time API v4»; нужен ответ администратора/вендора и фактический `/api/v4` capability check. До этого feasibility относится только к документированному Time.
2. **Исходящий webhook Time ограничен публичными каналами** (C2). Для private/DM нужен polling (C5) либо иная официально подтверждённая push-поверхность.
3. **Webhook HA — bearer-by-URL без отдельной auth** (C7). Если политика ИБ запрещает такой endpoint, понадобится reverse proxy/gateway с дополнительной аутентификацией или polling внутри доверенной сети.
4. **Неизвестны deployment flags и permissions.** Администратор Time может отключить incoming/outgoing webhooks, PAT и OAuth; необходимо подтвердить, что webhooks/bots разрешены (C1, C2, C4).
5. **Не найдены публичные rate limits/SLA/retry semantics** для `POST /posts` и polling. Нельзя назначить безопасную частоту production polling без нагрузочного лимита от владельца инстанса.

## leads

- Запросить у администратора Syncer/Time: server product name/build, API base URL, доступность `/api/v4/users/me`, bot accounts, incoming/outgoing webhooks, target channel type и ACL.
- Выполнить read-only capability probe ботом: `GET /api/v4/users/me`, затем тестовый `POST /api/v4/posts` в отдельный канал; проверить 401/403/404 и сертификат.
- Создать лабораторный outgoing webhook и сохранить фактический payload: поля token/post/user/channel, content type, retry при non-2xx, повторная доставка и порядок событий. Только после этого фиксировать validator/dedupe schema.
- Согласовать с ИБ сетевой маршрут Time→HA: VPN/private ingress, HA Cloud webhook либо reverse proxy с WAF/IP allowlist/mTLS, если поддерживается окружением.
- Проверить, доступен ли private-channel push в конкретной лицензии/версии или официальный WebSocket/event API; публичная документация этого раунда такого пути не подтвердила.

## not_found

- Официальное подтверждение соответствия продукта **Syncer** документированному **Time Messenger API**.
- Документированный официальный Home Assistant integration для Time/Syncer.
- Доказанный в прочитанных источниках контракт WebSocket/event stream Time, пригодный для HA.
- Документированный исходящий webhook Time из private/direct chat; найдено противоположное ограничение — только публичные каналы (C2).
- Полная публичная спецификация доставки outgoing webhook: подпись/HMAC, retry/backoff, timeout, ordering и idempotency guarantee.
- Публичные rate limits API v4 и заявленная совместимость API v4↔v5.

## Источники (8)

1. Time Messenger / T-Bank — [Управление интеграциями](https://docs.time-messenger.ru/administration/settings/integrations/integration_management/), n.d., accessed 2026-08-11.
2. Time Messenger / ООО «ТЦР» — [Персональные токены доступа](https://time-messenger.ru/documentation/personal-access-tokens/), n.d., accessed 2026-08-11.
3. Time Messenger / T-Bank — [Отправка сообщений](https://docs.time-messenger.ru/api/cookbook/send-a-message/), n.d., accessed 2026-08-11.
4. Time Messenger / T-Bank — [Получить посты для канала](https://docs.time-messenger.ru/api/v4/get-posts-for-channel/), n.d., accessed 2026-08-11.
5. Home Assistant Developer Docs / Open Home Foundation — [Notify entity](https://developers.home-assistant.io/docs/core/entity/notify/), updated 2026-03-24, accessed 2026-08-11.
6. Home Assistant / Open Home Foundation — [Automation triggers: Webhook trigger](https://www.home-assistant.io/docs/automation/trigger/#webhook-trigger), HA docs 2026.8.1, accessed 2026-08-11.
7. Home Assistant Developer Docs / Open Home Foundation — [Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/), n.d., accessed 2026-08-11.
8. Home Assistant / Open Home Foundation — [RESTful Command](https://www.home-assistant.io/integrations/rest_command/), HA docs 2026.8.1, accessed 2026-08-11.
