# Спека: личные сообщения Time Messenger в Home Assistant

Статус: реализовано (`0.0.1`–`0.0.3`). Архитектурные решения, на которые
ссылается этот документ, живут в [docs/architecture.md](../architecture.md).

## Зачем

Пользователю Home Assistant нужен единый сигнал о новых личных сообщениях
Time и безопасный поддерживаемый способ получить интеграцию.

## Возможности

- **Персональная авторизация.** Пользователь подключает свою учётную запись
  Time к Home Assistant. Каждый явно выбранный способ — OAuth, PAT или
  session — подтверждает identity через Time API и устанавливает
  авторизованный WebSocket; недействительные credentials запускают понятный
  reauth, а административно отключённый способ отображается как unsupported
  без утечки секрета.
- **Приём в реальном времени.** Событие Time `posted` для нового сообщения в
  1:1 канале типа `D`, адресованного авторизованному пользователю, поступает
  в обработку через WebSocket без polling как штатного транспорта.
- **Фильтрация чужих обычных сообщений.** Собственные сообщения,
  system/integration posts, неизвестные payload и каналы типов `G`, `P` или
  `O` не публикуют событие Home Assistant.
- **Дедупликация.** После первой успешной публикации повторная доставка
  того же `post_id` не создаёт новое событие в течение 24 часов или пока ID
  входит в 5000 новейших записей, включая reconnect и restart Home
  Assistant.
- **Расширяемое событие Home Assistant.** Автоматизации используют
  `time_messenger_event` со `schema_version: 1` и `type: direct_message`;
  текст доступен только после явного `include_message_text` opt-in. С
  версии 0.0.3 то же сообщение дополнительно доступно как нативная
  `EventEntity` в редакторе автоматизаций.
- **Восстановление после разрыва связи.** Единственный per-entry WebSocket
  listener переподключается по политике AD-5 из архитектуры, не оставляет
  zombie task после unload и не создаёт повторных событий для сохранённых
  `post_id`.

## Способы авторизации

Каждый способ реализует единый `TokenProvider` (AD-3). Пользователь выбирает
mode для конкретной ConfigEntry; автоматическое переключение между способами
запрещено.

| Способ | Настройка и хранение | Проверка и обновление | Unsupported / reauth |
| --- | --- | --- | --- |
| OAuth | Application Credential получает `auth_domain`, равный normalized tenant origin; custom implementation строит same-origin `/oauth/authorize` и `/oauth/access_token`. ConfigEntry хранит OAuth token, client credentials принадлежат Home Assistant `application_credentials`. Используется authorization code; implicit grant запрещён. | После выдачи или refresh `GET /api/v4/users/me` подтверждает identity, затем WebSocket получает `hello`. Refresh выполняется средствами OAuth adapter. | Нужны tenant client registration, scopes, PKCE policy и точный HA redirect URI. Terminal refresh failure запускает reauth того же mode. |
| PAT | Пользователь вставляет созданный им PAT; он хранится как bearer в `ConfigEntry.data`. | `users/me` и WebSocket `hello` проходят с тем же bearer; PAT действует до отзыва. | Администратор может отключить PAT; `401` запускает PAT reauth. Интеграция не предлагает другой mode автоматически. |
| Session | Config flow отправляет `login_id`, password и optional MFA в `POST /api/v4/users/login`; сохраняется только ответный header `Token`, password/MFA не сохраняются. | Ответный user и последующий `users/me` должны совпасть; WebSocket работает до завершения сессии. | Истечение/отзыв запускает session reauth. Если login endpoint запрещён SSO policy, mode показывается unsupported до появления документированного tenant flow; browser-login emulation запрещена. |

Общий security/lifecycle contract: bearer, password, MFA, client secret и
Authorization header не попадают в events, diagnostics, repr и обычные logs;
authenticated REST/WSS не следует redirects и не передаёт bearer за пределы
bound tenant origin; unload сохраняет credentials и только останавливает
runtime; удаление ConfigEntry очищает локальные OAuth/bearer данные и dedupe
Store, session выполняет best-effort logout.

## Ограничения

- Интеграционная поверхность — сервер Time Messenger; мобильный клиент не
  задаёт API-контракт.
- Time API v4 изолирован adapter boundary; основной транспорт — авторизованный
  WebSocket, REST используется только для identity/capability checks и
  metadata recovery.
- Bearer передаётся только по проверенному HTTPS/WSS на bound tenant origin;
  redirects, cross-origin forwarding и `verify_ssl: false` запрещены.
- `message_text` имеет тип `string|null`, по умолчанию `null` и
  сопровождается `text_redacted: true`; raw text никогда не попадает в logs
  или diagnostics.
- V1 не гарантирует REST backfill или gap-free доставку после полного
  офлайна.
- Target-tenant acceptance probe (AD-12) обязателен до заявления
  совместимости с новым сервером/tenant.

## Non-goals

- Исходящие сообщения Home Assistant → Time.
- Slash-команды, outgoing/incoming webhooks, внешний broker или companion
  daemon.
- Group direct (`G`), private (`P`) и public (`O`) каналы.
- Gap-free REST backfill.
- Device/sensor platforms и готовые device-specific автоматизации.
- Логика ламп, TTS или push-уведомлений внутри интеграции — это дело
  пользовательских автоматизаций.

## Сигнал успеха

Пользователь добавляет публичный repository как HACS custom integration,
устанавливает релиз, проходит native config flow и получает ровно один
`time_messenger_event` (и, начиная с 0.0.3, одно срабатывание `EventEntity`)
на новое чужое сообщение в 1:1 Time-чате.
