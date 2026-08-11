# Верификация API и интеграционных поверхностей Time Messenger

Дата проверки: 2026-08-11  
Режим: fresh-context, normal validation, spot-check несущих утверждений  
Проверены только `integration-api-r1-1.md`, `integration-api-r2-1.md` и семь прямо указанных в них страниц Time. Другие проектные файлы не читались.

## Итог

Позитивные утверждения о REST API v4/OpenAPI, PAT, incoming webhook, slash-command token и WebSocket endpoint/auth/event envelope семантически подтверждаются первичной документацией. Существенные оговорки нужны для v5, bot-токенов, подробной модели outgoing webhook и гарантий доставки: просмотренные страницы либо не дают заявленных деталей, либо позволяют подтвердить только отсутствие сведений **на конкретной странице**, но не их отсутствие во всей документации или реализации.

Все семь открытых источников принадлежат одному издателю — Time Messenger / T‑Bank. Поэтому `verified` ниже означает прямое подтверждение авторитетным первичным источником, но не независимый cross-publisher check и не runtime-проверку целевого инстанса.

## Outcomes по несущим claims

| Claim | Outcome | Проверка и коррекция | Confidence |
|---|---|---|---|
| REST API v4 использует базовый путь `/api/v4`, JSON и опубликованный `openapi.yaml`, пригодный для генерации SDK | **verified** | Страница схемы дословно подтверждает HTTPS `/api/v4`, `application/json`, ссылку на OpenAPI и генерацию клиентских SDK. Это подтверждает наличие спецификации, но не её полноту или отсутствие drift относительно сервера. | high для документированного контракта; medium для фактического parity без runtime-теста |
| Документация API v5 существует, имеет `Version: 5.0` и `Authorization` API key `access_token` | **verified** | Страница v5 это подтверждает. | high |
| v4 остаётся «основным» контуром; для v5 нет migration/deprecation/parity matrix | **unverified** | Одновременное наличие разделов v4 и v5 подтверждено, а открытая landing page v5 показывает ограниченный набор групп. Но одна landing page и ограниченный поиск не доказывают ни приоритет v4, ни глобальное отсутствие migration guide/changelog. Формулировать как: «в просмотренных страницах матрица не найдена; проверять нужные методы и версию сервера отдельно». | medium для практической рекомендации; low для глобального negative claim |
| PAT передаётся как Bearer и живёт до ручного отзыва; session token выдаётся после `POST /api/v4/users/login` | **verified** | Страница аутентификации подтверждает login endpoint, заголовок `Token`, дальнейший `Authorization: Bearer`, а также срок жизни PAT до ручного отзыва. | high |
| Bot account/token пригоден для REST; у бота может быть несколько активных токенов | **unverified** | В пределах открытых семи страниц bot-token semantics не показаны. Наличие раздела «Боты» в навигации не подтверждает способ аутентификации, число токенов или их lifecycle. В итоговом отчёте PAT можно утверждать уверенно; bot token — оставлять со ссылкой на отдельную страницу создания/токенов бота либо пометить непроверенным. | low в этой проверке |
| Incoming webhook вызывается `POST /hooks/:hook_id` | **verified** | Endpoint и ответы 200/400/401/403/404 прямо видны. | high |
| Incoming webhook не имеет отдельной подписи/HMAC, request schema и отдельной авторизации | **unverified** | Подтверждено только, что открытая endpoint-страница не отображает request schema и HMAC/signature. Ответ 401 с текстом «токен доступа не предоставлен» создаёт неоднозначность: нельзя утверждать, что `hook_id` — единственный credential. Коррекция: URL следует защищать как секрет, но необходимость дополнительного Bearer token проверить на реальном сервере/OpenAPI. | high для page-level omission; low для API-wide negative claim |
| Outgoing webhook существует; список — `GET /api/v4/hooks/outgoing`, фильтр по team/channel, permission `manage_webhooks` | **verified** | Endpoint, фильтрация и permission подтверждены страницей списка. | high |
| Outgoing webhook ограничен публичным каналом и содержит `trigger_words`, `trigger_when`, `callback_urls`, JSON/form content types | **unverified** | В открытом HTML страницы списка эти поля не отображаются. Возможно, они присутствуют в скрытой OpenAPI schema, но текущий spot-check этого не подтвердил. Нельзя переносить «public-channel limit» на slash commands: в проверенной slash-command странице такого ограничения нет. | medium-low до проверки OpenAPI/create-outgoing schema |
| Slash command использует GET query или POST form-urlencoded и передаёт статический `token` для валидации источника; токен после создания повторно не показывается | **verified** | Cookbook буквально подтверждает методы, content type, полный набор основных полей, назначение token и одноразовый показ. Это статический shared secret, а не документированная HMAC-подпись. | high |
| WebSocket доступен на `/api/v4/websocket`, поддерживает cookie/Authorization или `authentication_challenge`, имеет envelope `event/data/broadcast/seq` | **verified** | Endpoint, оба способа auth, `status: OK`, `seq_reply`, событие `hello` и envelope подтверждены. | high |
| WebSocket покрывает сообщения, редактирование/удаление, реакции, typing, channel/thread/user/status и файл-события | **verified** с коррекцией | Список подтверждает `posted`, `post_edited`, `post_deleted`, реакции, typing, конкретные channel/thread/user/status events и **только `file_deleted`** среди file events. Формулировки «события файлов» или `channel_*` не должны подразумевать произвольные wildcard/создание/загрузку файлов. | high для перечисленного surface; low для любых неявных file events |
| WebSocket/outgoing webhook не имеют heartbeat, retries, replay/resume, ack, ordering или delivery guarantees | **unverified** как глобальный claim | На открытой WebSocket-странице такие semantics действительно не описаны; открытая страница списка outgoing webhook также не показывает delivery policy. Но это доказывает лишь page-level omission, не отсутствие сведений во всей документации или поведения в реализации. Инженерный вывод — считать delivery best-effort до подтверждения и делать idempotency + reconnect + REST resync — разумен, но остаётся архитектурной рекомендацией. | high для page-level omission; medium для defensive pattern; low для глобального отрицания |

## Обязательные правки для синтеза

1. Разделить утверждение о v5 на подтверждённый факт существования v5 и непроверенное отсутствие общей migration/deprecation matrix. Не называть v4 «основным» без критерия.
2. Не объединять bot и PAT auth: PAT подтверждён; bot token/multiple-token lifecycle в этой проверке не подтверждены.
3. Не утверждать, что `hook_id` — единственная авторизация incoming webhook: сама страница перечисляет 401 «токен доступа не предоставлен».
4. Привязку к публичному каналу относить только к outgoing webhook и только после проверки schema/create endpoint; slash-command cookbook такого ограничения не задаёт.
5. Сузить WebSocket file surface до документированного `file_deleted`; заменить wildcard-формулировки перечислением реально опубликованных events.
6. Заменить «гарантий доставки нет» на «на просмотренных страницах гарантии/replay/retry/ordering не документированы; до подтверждения поставщиком проектировать как best-effort».

## Источники проверки (7)

1. Time API v4 — Schema: https://docs.time-messenger.ru/api/v4/%D1%81%D1%85%D0%B5%D0%BC%D0%B0/
2. Time API v5 — Reference: https://docs.time-messenger.ru/api/v5/time-api-reference/
3. Time API v4 — Authentication: https://docs.time-messenger.ru/api/v4/%D0%B0%D1%83%D1%82%D0%B5%D0%BD%D1%82%D0%B8%D1%84%D0%B8%D0%BA%D0%B0%D1%86%D0%B8%D1%8F/
4. Time API v4 — Use incoming webhook: https://docs.time-messenger.ru/api/v4/use-incoming-webhook/
5. Time API v4 — List outgoing webhooks: https://docs.time-messenger.ru/api/v4/get-outgoing-webhooks/
6. Time API Cookbook — Slash commands: https://docs.time-messenger.ru/api/cookbook/slash-commands/
7. Time API v4 — WebSocket: https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/

