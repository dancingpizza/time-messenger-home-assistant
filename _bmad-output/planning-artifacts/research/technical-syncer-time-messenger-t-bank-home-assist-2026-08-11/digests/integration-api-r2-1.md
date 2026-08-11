# Раунд 2 — lead-following по webhook, slash commands, OAuth2 и WebSocket Time

Дата исследования: 2026-08-11  
Область: сервер/API Time Messenger. Уточнение, что Syncer является мобильным клиентом Time, использовано только для ограничения темы и не считается внешним доказательством.  
Метод: прочитаны пять конкретных официальных страниц; проектные файлы и проектный контекст не использовались как источник фактов.

## Краткий вывод

Самый хорошо специфицированный путь Time → Home Assistant — slash-команда: документированы GET/POST, form/query payload, проверочный `token`, идентификаторы пользователя/канала/пространства и синхронный либо отложенный ответ через `response_url`. Обычный outgoing webhook подходит для триггеров сообщений из публичного канала и позволяет выбрать callback URL и content type, но открытая документация не задает callback payload, подпись, timeout, retry/backoff или гарантию доставки. Incoming webhook документирован как `POST /hooks/:hook_id`, однако его wire payload и криптографическая проверка также не раскрыты.

Для пользовательской делегации Time документирует OAuth2 Authorization Code и Implicit Grant, refresh token и точное совпадение `redirect_uri`, но не scopes, PKCE, срок жизни токенов или требования к `state`. Для событий WebSocket остается предпочтительнее polling, но клиент должен самостоятельно реализовать reconnect и REST-resync: replay/resume/ack guarantees не найдены.

## Claims

### C1 — incoming webhook: endpoint и границы спецификации

- **claim:** Входящий webhook вызывается `POST /hooks/:hook_id`; документация допускает переопределение отдельных полей и перечисляет ответы 200, 400, 401, 403 и 404. На самой endpoint-странице нет схемы request body, перечня разрешенных полей, content type, лимита размера, idempotency key, подписи запроса или отдельного заголовка авторизации.
- **URL:** https://docs.time-messenger.ru/api/v4/use-incoming-webhook/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high для endpoint/status; high для отсутствия сведений на прочитанной странице
- **class:** integration

### C2 — `hook_id` находится в URL, отдельная подпись не документирована

- **claim:** Единственный явно показанный идентификатор/секрет вызова incoming webhook — `:hook_id` в URL. Публичная страница не описывает HMAC-подпись, timestamp/nonce или ротацию секрета для входящего вызова; поэтому URL целиком следует трактовать как секрет и не логировать. Последнее — архитектурный вывод, не заявленная гарантия Time.
- **URL:** https://docs.time-messenger.ru/api/v4/use-incoming-webhook/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high для наблюдаемого API; medium для рекомендации
- **class:** security

### C3 — конфигурация outgoing webhook

- **claim:** Объект исходящего webhook содержит `team_id`, `channel_id` публичного канала, `trigger_words`, `trigger_when` (`0` — слово в любом месте, `1` — сообщение начинается со слова), массив `callback_urls` и `content_type`; поддерживаются `application/json` и `application/x-www-form-urlencoded`, по умолчанию form-urlencoded. Список можно фильтровать по команде и каналу.
- **URL:** https://docs.time-messenger.ru/api/v4/get-outgoing-webhooks/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** integration

### C4 — права на управление outgoing webhooks

- **claim:** Для чтения списка исходящих webhooks требуется `manage_webhooks` на уровне системы либо соответствующей команды/канала; endpoint использует Bearer token. Это административное permission для конфигурации, а не описание проверки callback-запроса на стороне получателя.
- **URL:** https://docs.time-messenger.ru/api/v4/get-outgoing-webhooks/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** security

### C5 — outgoing webhook не является общим event bus

- **claim:** Документированная модель outgoing webhook привязана к одной команде/публичному каналу и trigger words. Следовательно, для Home Assistant это фильтрованный message trigger, а не документированная подписка на все события Time; для реакций, изменений постов, файлов и системных событий следует использовать WebSocket или отдельный REST reconciliation.
- **URL:** https://docs.time-messenger.ru/api/v4/get-outgoing-webhooks/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high для модели; medium для архитектурного вывода
- **class:** integration

### C6 — slash command request payload и проверка источника

- **claim:** Slash-команда отправляет GET query parameters либо POST body с `Content-Type: application/x-www-form-urlencoded`. Документированы поля `channel_id`, `channel_name`, `command`, `response_url`, `team_domain`, `team_id`, `text`, `token`, `user_id`, `user_name`, `root_id`. Поле `token` предназначено для проверки подлинности источника запроса; значение показывается при создании команды и позднее повторно не отображается.
- **URL:** https://docs.time-messenger.ru/api/cookbook/slash-commands/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** security

### C7 — slash command response payload

- **claim:** Немедленный JSON-ответ может содержать `response_type` (`in_channel` или `ephemeral`), `text`, `username`, `channel_id`, `icon_url`, `type`, `props`, `goto_location`, `skip_slack_parsing` и `extra_responses`. Для отложенного ответа передается `response_url`; отдельный endpoint ответа имеет вид `/hooks/commands/:hook_id`.
- **URL:** https://docs.time-messenger.ru/api/cookbook/slash-commands/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** integration

### C8 — OAuth2 registration и Authorization Code flow

- **claim:** Time может быть OAuth2 service provider. Администратор должен включить функцию, затем приложение регистрирует homepage и callback URL и получает `Client ID`/`Client Secret`. Authorization Code flow использует `/oauth/authorize` с `response_type=code`, `client_id`, `redirect_uri`; redirect URI должен точно совпадать с зарегистрированным. Обмен code и refresh выполняется POST на `/oauth/access_token`, ответы содержат access/refresh tokens.
- **URL:** https://docs.time-messenger.ru/integrations/oauth2_service_provider/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** security

### C9 — OAuth2 Implicit Grant и недокументированные защитные параметры

- **claim:** Time также документирует Implicit Grant: `/oauth/authorize?response_type=token...` возвращает access token во fragment redirect URL. На странице не описаны scopes, PKCE, обязательный `state`, срок жизни access/refresh tokens, rotation refresh token, client-credentials flow или device flow; пример Go вызывает `AuthCodeURL("")`, то есть сам пример не передает state.
- **URL:** https://docs.time-messenger.ru/integrations/oauth2_service_provider/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high для опубликованных flows и содержимого страницы
- **class:** security

### C10 — WebSocket auth, envelope и события

- **claim:** WebSocket endpoint — `/api/v4/websocket`. Аутентификация возможна cookie/Authorization или после подключения сообщением `{"seq":1,"action":"authentication_challenge","data":{"token":"…"}}`; успех — `status: OK`, `seq_reply`, затем событие `hello` с версией сервера. Event envelope содержит `event`, `data`, `broadcast` и `seq`; документированы `posted`, `post_edited`, `post_deleted`, реакции, typing, channel/thread/user events и `file_deleted`.
- **URL:** https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** integration

### C11 — WebSocket delivery semantics не специфицированы

- **claim:** Прочитанная WebSocket-страница не документирует heartbeat/ping policy, reconnect backoff, retention/replay, resume cursor, acknowledgement, ordering across reconnects, at-least-once/exactly-once semantics или предел очереди. Для HA надежность необходимо получить через reconnect + идемпотентную обработку по ID объекта + REST resync после разрыва; это инженерный вывод из отсутствия гарантий, а не гарантия поставщика.
- **URL:** https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high для отсутствия сведений на странице; medium для паттерна HA
- **class:** integration

### C12 — публичной migration/deprecation matrix v4↔v5 не обнаружено

- **claim:** Официальный поиск документации нашел параллельные справочники v4 и v5, но не выявил migration guide, deprecation schedule, compatibility matrix или API-specific changelog, объясняющий замену методов v4 методами v5. Поэтому миграцию нельзя планировать по номеру версии: совместимость каждого нужного метода должна проверяться по текущим схемам и на целевом сервере.
- **URL:** https://docs.time-messenger.ru/api/v5/time-api-reference/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** medium (negative finding после четырех различных официально-ограниченных запросов)
- **class:** version-compatibility

## Практическое следствие для Home Assistant

1. Для команды пользователя предпочтителен slash-command endpoint HA: проверять `token` constant-time сравнением, дополнительно allowlist `team_id`/`channel_id`, немедленно возвращать короткий JSON, а долгую работу завершать через `response_url`.
2. Для обычного outgoing webhook считать доставку best-effort до подтверждения поставщиком: endpoint HA должен быстро вернуть 2xx, быть идемпотентным и журналировать собственный correlation ID без секрета.
3. Для HA → Time входящий webhook использовать как минимальный transport уведомлений, но сначала прототипом определить фактический JSON/form payload и допустимые override fields на конкретной версии сервера.
4. Для широкой событийной интеграции использовать WebSocket и восстанавливать пропуски через REST; outgoing webhook не заменяет event stream.
5. Для одного технического инстанса HA bot/PAT проще OAuth. OAuth Authorization Code полезен, если доступ должны делегировать разные пользователи; реализация должна самостоятельно добавить и проверять `state`, а доступность PKCE/scopes — уточнить у Time.

## Contradictions / tensions

- Endpoint incoming webhook возвращает среди вариантов 401 «токен доступа не предоставлен», но путь одновременно содержит `:hook_id`, и страница не объясняет, требуется ли еще Bearer token либо `hook_id` и есть token. Это неоднозначность спецификации, требующая проверки реальным запросом.
- OAuth-страница называет поддерживаемым Implicit Grant и публикует пример Authorization Code без `state`; при этом не объясняет CSRF-защиту или PKCE. Это не внутреннее логическое противоречие API, но существенный security gap документации.
- В v4 встречаются endpoint-level минимальные версии сервера, однако не найдена единая матрица v4/v5. Наличие обоих справочников не доказывает ни полный паритет, ни депрекацию v4.

## Not found

- **Incoming webhook:** request schema/payload examples, content type, максимальный размер, обязательные поля, idempotency, HMAC/signature, timestamp/nonce, IP ranges, secret rotation, URL expiry.
- **Outgoing webhook:** фактический callback payload, где и как передается проверочный token, подпись/HMAC, TLS/URL scheme restrictions, allow/deny private or loopback hosts beyond the public-channel binding, DNS rebinding/SSRF protections.
- **Delivery:** timeout запроса, число retries, backoff, условия повторной доставки, порядок, дедупликационный event ID, dead-letter behavior, SLA/at-least-once/exactly-once guarantee.
- **Slash commands:** timeout синхронного ответа, срок жизни `response_url`, повторная доставка команды, подпись сильнее статического form/query token, ограничения callback URL.
- **OAuth2:** scopes/permissions consent model, PKCE, обязательный `state`, token TTL, refresh rotation/reuse policy, revocation endpoint protocol, client credentials/device flow.
- **WebSocket:** ping/heartbeat, reconnect policy, resume/replay cursor, ack, delivery/ordering guarantees, лимиты сообщения/буфера.
- **Versions:** публичная migration/deprecation matrix v4↔v5, API-specific changelog или дата отключения v4.

## Прочитанные официальные источники (5)

1. Incoming webhook endpoint: https://docs.time-messenger.ru/api/v4/use-incoming-webhook/
2. Outgoing webhook schema/list: https://docs.time-messenger.ru/api/v4/get-outgoing-webhooks/
3. Slash commands cookbook: https://docs.time-messenger.ru/api/cookbook/slash-commands/
4. OAuth2 Service Provider: https://docs.time-messenger.ru/integrations/oauth2_service_provider/
5. WebSocket v4: https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/

