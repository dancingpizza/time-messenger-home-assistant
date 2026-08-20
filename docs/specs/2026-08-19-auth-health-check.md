# Спека: периодическая проверка авторизации

Статус: реализовано, релиз `0.0.6` (2026-08-20).

## Зачем

После успешной авторизации WebSocket может оставаться открытым, даже если
PAT, OAuth token или session token уже отозван. Без отдельной проверки Home
Assistant узнаёт об этом только при следующем REST-запросе или переподключении
WebSocket. Пользователь может долго не получать сообщения и не видеть, что
интеграции нужна повторная авторизация.

## Контракт проверки

Каждая загруженная ConfigEntry выполняет authenticated
`GET /api/v4/users/me` через существующий Time v4 adapter. Первая проверка
проходит во время setup gate; после запуска runtime отдельная health task
повторяет её с базовым интервалом 15 минут и jitter `±10%`. Jitter применяется
к каждой следующей задержке, поэтому проверки разных ConfigEntry не должны
синхронизироваться после общего запуска Home Assistant.

Результат классифицируется так:

| Результат | Действие |
| --- | --- |
| `200`, `id` совпадает с bound `user_id` | Авторизация здорова; listener продолжает работу. |
| `200`, `id` отличается от bound `user_id` | Identity mismatch считается auth failure; listener останавливается, ConfigEntry reload-ится и переходит в reauth. |
| `401` | Credentials больше не принимаются; listener останавливается, ConfigEntry reload-ится и переходит в reauth. |
| Terminal OAuth refresh failure | Listener останавливается, ConfigEntry reload-ится и переходит в OAuth reauth. |
| DNS, timeout, `429`, `5xx` или transient OAuth refresh failure | Reauth не запускается; работающий listener не останавливается, а health-check повторяется по retry policy. |
| `400`, `404` или malformed response | Protocol failure не доказывает, что credentials недействительны; listener остаётся активным, проверка повторяется позднее. |

Для `429` adapter разбирает bounded `Retry-After` или rate-limit reset, а
следующий плановый health-check происходит позже этой задержки. Transient
health failure не доказывает недействительность credentials и поэтому не
должен превращать временную недоступность REST API в запрос повторного входа.

Time не документирует, считается ли такой REST-запрос активностью, которая
продлевает session token при включённом server-side продлении сессий. Поэтому
health-check гарантирует обнаружение явного отказа credentials, но не обещает
пассивно дождаться idle expiration на tenant с продлением по активности.

## Runtime и Home Assistant

ConfigEntry владеет одним supervised WebSocket listener и одной runtime-owned
health task. Health task не является transport для сообщений и не заменяет
WebSocket reconnect supervisor.

Позднее [спека scheduled online keeper](2026-08-19-scheduled-online-keeper.md)
добавила третью, строго optional task. Она не меняет cadence или read-only
контракт auth health, но участвует в общей generation/cancellation.

При auth failure runtime сначала инвалидирует текущую generation и закрывает
WebSocket, затем один раз планирует reload той же ConfigEntry. Повторный setup
проходит тот же identity/capability gate и преобразует подтверждённый отказ в
стандартный `ConfigEntryAuthFailed`. Home Assistant переводит entry в
`setup_error`, выделяет карточку интеграции красным и сам создаёт системное
требование повторной авторизации в Repairs, которое видно на главном экране
настроек. Отдельный sensor, event или custom Repair issue для этого не
создаётся. После успешного reauth новый reload проходит полный gate и запускает
новый runtime.

### Почему reload, а не прямой reauth

Это решение нужно для двух разных UI-сигналов Home Assistant, которые имеют
разные источники состояния:

1. `ConfigEntry.async_start_reauth(hass)` запускает reauth flow и для
   незавершённого flow создаёт стандартный Repairs issue. Frontend показывает
   такой flow отдельной красной attention-карточкой, а issue — на главном
   экране настроек. Но состояние уже загруженной ConfigEntry остаётся
   `loaded`, поэтому исходная карточка интеграции не краснеет.
2. Исходная карточка интеграции получает красный стиль только для error-state,
   в том числе `setup_error`. Публичного API для принудительной установки этого
   состояния из произвольной background task нет.
3. Поэтому подтверждённый `AuthError` планирует публичный
   `hass.config_entries.async_schedule_reload(entry_id)`. Повторный setup первым
   делом выполняет identity check, преобразует тот же отказ в
   `ConfigEntryAuthFailed`, а Core штатно ставит `setup_error` и запускает
   reauth. В результате краснеет исходная карточка, появляется отдельная
   reauth-карточка и создаётся Repairs issue.

Последовательность состояния:

```text
LOADED
  -> health/listener получает подтверждённый AuthError
  -> runtime инвалидирует generation и закрывает WebSocket
  -> async_schedule_reload(entry_id)
  -> setup: GET /api/v4/users/me -> AuthError -> ConfigEntryAuthFailed
  -> SETUP_ERROR + reauth flow + системный Repairs issue
  -> успешный reauth обновляет credentials и планирует reload
  -> полный identity/capability gate
  -> LOADED с новым runtime
```

Reload Home Assistant сначала завершает уже открытый reauth/reconfigure flow.
Чтобы фоновая проверка не закрыла форму прямо во время ввода новых данных,
runtime перед reload проверяет активные flows. Если такой flow уже есть, socket
и listener останавливаются, но новый reload не планируется: существующая
attention-карточка и Repairs issue уже дают пользователю нужный путь ремонта.

Решение сверено с зафиксированной для проекта версией Home Assistant 2026.8.1:

- Core обрабатывает `ConfigEntryAuthFailed`, запускает reauth и затем ставит
  `SETUP_ERROR`: [config_entries.py](https://github.com/home-assistant/core/blob/2026.8.1/homeassistant/config_entries.py#L793-L832),
  [установка state](https://github.com/home-assistant/core/blob/2026.8.1/homeassistant/config_entries.py#L923-L932);
- Core создаёт системный reauth Repairs issue:
  [config_entries.py](https://github.com/home-assistant/core/blob/2026.8.1/homeassistant/config_entries.py#L1346-L1361);
- frontend красит обычную integration-card по `setup_error`, а reauth flow
  показывает отдельной attention-card:
  [integration-card](https://github.com/home-assistant/frontend/blob/235541748ba1c291171d3ec759dd473685c8f2be/src/panels/config/integrations/ha-integration-card.ts#L45-L96),
  [flow-card](https://github.com/home-assistant/frontend/blob/235541748ba1c291171d3ec759dd473685c8f2be/src/panels/config/integrations/ha-config-flow-card.ts#L51-L95);
- главный config dashboard выводит незаглушённые Repairs issues:
  [ha-config-dashboard.ts](https://github.com/home-assistant/frontend/blob/235541748ba1c291171d3ec759dd473685c8f2be/src/panels/config/dashboard/ha-config-dashboard.ts#L276-L303).

Отвергнутые варианты:

- прямой `async_start_reauth()` — не красит исходную integration-card;
- ручное изменение приватного state ConfigEntry — опирается на внутренний API
  Core и обходит lifecycle;
- собственный Repairs issue — дублирует стандартный issue и требует вручную
  синхронизировать его создание и удаление;
- frontend/CSS override — не относится к ответственности backend-интеграции и
  нестабилен между версиями Home Assistant.

Unload инвалидирует generation, отменяет и ожидает все runtime-задачи и
закрывает socket. Late health callback от прежней generation не может запустить
reload. Одновременные health requests для одной ConfigEntry запрещены. Если
reauth или reconfigure этой entry уже открыт, runtime останавливается, но не
планирует новый reload и не сбрасывает форму, в которую пользователь уже
вводит данные.

## Способы авторизации

- OAuth provider перед запросом обеспечивает актуальность access token. Только
  terminal refresh failure считается auth failure; `429`, `5xx` и сетевые
  ошибки refresh остаются transient. Плановый token-only update от OAuth
  provider не reload-ит runtime; privacy options reload-ятся через
  `OptionsFlowWithReload`, а успешный reauth явно планирует reload. Если OAuth
  Application Credentials были удалены, reauth остаётся открытым и сохраняет
  Repairs-действие, пока пользователь не восстановит credentials.
- PAT и session используют сохранённый bearer без автоматического обновления;
  действительность подтверждает `/api/v4/users/me`.
- Reauth всегда сохраняет выбранный `auth_mode`, bound tenant origin и identity.
  Автоматический fallback между OAuth, PAT и Session запрещён.

## Безопасность

Health-check использует тот же redirect-refusing HTTPS client и тот же bound
tenant origin, что setup и metadata requests. Bearer, refresh token,
Authorization header и response body не попадают в logs, diagnostics, events
или Repairs issue. В diagnostics допустимы только несекретные агрегированные
состояния и timestamps, если они понадобятся позже.

## Non-goals

- Настраиваемый пользователем интервал проверки.
- Token introspection endpoint или вывод срока действия token в интерфейсе.
- Проверка credentials на каждом сообщении WebSocket.
- Использование health-check как индикатора доступности всего tenant или как
  замена WebSocket heartbeat.
- Автоматическая смена способа авторизации.

## Проверка реализации

Автоматические тесты фиксируют как минимум:

- jittered delay остаётся в диапазоне от 13,5 до 16,5 минуты;
- `200` с той же identity оставляет listener активным;
- `401`, identity mismatch и terminal OAuth refresh failure планируют ровно
  один reload, после которого setup выдаёт `ConfigEntryAuthFailed`, и
  останавливают listener;
- transient failure, `429` и `5xx` не запускают reauth и не закрывают рабочий
  WebSocket;
- health requests одной ConfigEntry не перекрываются;
- unload и смена generation блокируют late reauth;
- активный reauth/reconfigure flow не сбрасывается повторным reload;
- ни один auth mode не раскрывает token в logs или diagnostics.
