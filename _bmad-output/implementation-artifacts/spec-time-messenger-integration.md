---
title: 'Интеграция Time Messenger для личных сообщений'
type: 'feature'
created: '2026-08-11'
status: 'done'
review_loop_iteration: 0
baseline_commit: '9faafd042c51d2f3f479290ecde9736ac98dbc86'
context:
  - '{project-root}/_bmad-output/specs/spec-syncer-time-messenger-t-bank-home-assist/SPEC.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-syncer-ha-2026-08-11/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Home Assistant не получает личные сообщения корпоративного Time, поэтому пользователь не может запускать расширяемые автоматизации по факту нового сообщения.

**Approach:** Создать async custom integration с нативным config flow для OAuth, PAT и Session, одним supervised WebSocket на аккаунт, fail-closed фильтрацией, durable dedupe и событием `time_messenger_event` schema v1.

## Boundaries & Constraints

**Always:** Соблюдать CAP-1–CAP-6 и AD-1–AD-13. Одна ConfigEntry = один `(tenant origin, user_id)`; несколько записей изолированы. REST и WSS используют TLS и не следуют redirect; bearer не покидает bound origin. Принимать только обычный `posted` (`post.type == ""`) из канала `D` от другого пользователя. Сохранять dedupe до публикации. `message_text=null` до opt-in. Все I/O async, secrets и текст исключены из logs/diagnostics.

**Ask First:** Ослабление TLS/same-origin, изменение публичной event schema, добавление tenant-specific undocumented workaround, custom frontend или расширение scope на каналы `G/P/O` и backfill.

**Never:** Скрытый auth fallback, polling как штатный transport, `verify_ssl: false`, browser-login emulation, webhook/broker/daemon, EventEntity/device entities, встроенные действия света/TTS/push.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Auth | OAuth, PAT или login+optional MFA | `users/me`, WS challenge и `hello`; immutable identity | `401` → same-mode reauth; disabled mode → unsupported |
| Session | Login возвращает любой `2xx` + header `Token` | Сохранить только bearer и user | Нет `Token` → protocol error; password/MFA не сохранять |
| Direct post | `posted`, `data.post` string/object, type `D`, чужой author | Канонический message → dedupe → один HA event | Malformed/unknown → drop fail-closed |
| Channel metadata | `channel_type` отсутствует/невалиден | `GET /channels/{id}`, затем cache | Lookup failure → transient/drop без события |
| Duplicate | Повторный `post_id` после reconnect/restart | Не публиковать в пределах 24h/5000 IDs | Store failure → не публиковать |
| Privacy | `include_message_text=false/true` | `null,true` / полный текст,false | Raw text никогда не логировать |
| Disconnect | DNS/timeout/5xx/429 либо auth failure | jitter reconnect 1..60s или reauth | Unload invalidates generation и ждёт task |
| Removal | ConfigEntry удалена | local token/dedupe purge; session logout best-effort | Remote failure не блокирует local cleanup |

</frozen-after-approval>

## Code Map

- `pyproject.toml` — Python 3.14/HA 2026.8.1 test and lint environment; `UV_CACHE_DIR` должен быть workspace/tmp-local.
- `custom_components/time_messenger/{manifest.json,const.py,models.py}` — domain, schema v1 и immutable canonical models.
- `custom_components/time_messenger/api/{auth.py,client.py,websocket.py,exceptions.py}` — единственный Time v4 wire boundary; login token из response header; tolerant `posted` parser.
- `custom_components/time_messenger/{pipeline.py,dedupe.py,event.py}` — pure filtering, atomic `Store` check-and-save и HA publisher.
- `custom_components/time_messenger/{runtime.py,__init__.py}` — generation-guarded supervisor, ConfigEntry lifecycle и removal cleanup.
- `custom_components/time_messenger/{config_flow.py,application_credentials.py}` — native PAT/session/OAuth setup, same-mode reauth, options; tenant origin нельзя менять через reconfigure.
- `custom_components/time_messenger/{diagnostics.py,translations/en.json,translations/ru.json}` — allowlisted diagnostics и UI/Repair copy; custom integration не использует `strings.json`.
- `tests/components/time_messenger/` — unit/integration tests; production tree отсутствует, поэтому reuse points нет.
- `scripts/probe_time_tenant.py` — ручной AD-12 acceptance probe без secrets в output.

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml`, `custom_components/time_messenger/manifest.json`, translations — создать минимальный installable/testable scaffold.
- [x] `tests/components/time_messenger/test_pipeline.py`, `test_event.py`, `test_dedupe.py` → соответствующие production modules — RED/GREEN для canonical filtering, privacy event и persistent replay suppression.
- [x] `tests/components/time_messenger/test_api.py` → `api/` — RED/GREEN для URL safety, login/OAuth/REST, tolerant post parsing, channel cache и redirect-safe WS challenge.
- [x] `tests/components/time_messenger/test_runtime.py` → `runtime.py`, `__init__.py` — RED/GREEN для single listener, backoff, generation guard, unload/remove.
- [x] `tests/components/time_messenger/test_config_flow.py` → `config_flow.py`, `application_credentials.py` — RED/GREEN для трёх mode, unique identity, same-mode reauth и privacy options.
- [x] `tests/components/time_messenger/test_diagnostics.py`, fixtures, `scripts/probe_time_tenant.py` — проверить redaction и tenant acceptance contract.

**Acceptance Criteria:**
- Given валидный enabled auth mode, when setup проходит identity и `hello`, then ровно один listener принадлежит ConfigEntry.
- Given чужой обычный post в `D`, when он доставлен повторно, then публикуется один schema-v1 event и `post_id` переживает restart.
- Given self/system/malformed/`G/P/O` input, when pipeline обрабатывает его, then HA event не возникает.
- Given terminal auth failure, when runtime его классифицирует, then запускается reauth того же mode без fallback.
- Given transient disconnect or 429, when supervisor retries, then соблюдаются bounded jitter/rate-limit delay и unload не оставляет callback/task.
- Given diagnostics or logs, when они сформированы, then bearer, OAuth token, password, MFA и message text отсутствуют.
- Given удаление ConfigEntry, when remote logout недоступен, then local credentials и Store всё равно удалены.

## Spec Change Log

## Design Notes

Для WSS использовать HA-created entry-owned `aiohttp` session с `TraceConfig.on_request_redirect`, который прерывает handshake; token отправлять только WebSocket challenge после соединения. REST задаёт `allow_redirects=False`. `data.post` принимает object либо JSON string; `channel_type` при отсутствии резолвится отдельным v4 call. Store создаётся private + atomic и сохраняется немедленно до `hass.bus.async_fire`.

## Verification

**Commands:**
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv sync --all-groups` — зависимости разрешены и lock актуален.
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run pytest` — все behavioral tests проходят без warnings.
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run ruff check .` — lint clean.
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run ruff format --check .` — formatting clean.
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run mypy custom_components/time_messenger` — typed runtime clean.

## Suggested Review Order

**Lifecycle и устойчивость**

- Entry gate связывает identity, capability, listener и гарантированную очистку.
  [`__init__.py:57`](../../custom_components/time_messenger/__init__.py#L57)

- Supervisor разделяет reauth, terminal Repair и bounded transient retry.
  [`runtime.py:89`](../../custom_components/time_messenger/runtime.py#L89)

- Removal отделяет remote logout от безусловной локальной очистки.
  [`__init__.py:144`](../../custom_components/time_messenger/__init__.py#L144)

**Безопасная граница Time API**

- WebSocket listener доставляет только разобранные `posted` в generation-guarded pipeline.
  [`websocket.py:109`](../../custom_components/time_messenger/api/websocket.py#L109)

- Dual-signal handshake требует challenge ACK и `hello` в любом порядке.
  [`websocket.py:180`](../../custom_components/time_messenger/api/websocket.py#L180)

- REST boundary запрещает redirects и нормализует auth, rate-limit и transient ошибки.
  [`client.py:164`](../../custom_components/time_messenger/api/client.py#L164)

- Wire parser fail-closed принимает документированные и tolerant формы `posted`.
  [`client.py:259`](../../custom_components/time_messenger/api/client.py#L259)

**Фильтрация, дедупликация и событие**

- Pipeline допускает только чужие обычные сообщения из direct-каналов.
  [`pipeline.py:36`](../../custom_components/time_messenger/pipeline.py#L36)

- Durable Store сохраняет post ID атомарно до публикации события.
  [`dedupe.py:22`](../../custom_components/time_messenger/dedupe.py#L22)

- Schema v1 сохраняет текст скрытым до явного privacy opt-in.
  [`event.py:10`](../../custom_components/time_messenger/event.py#L10)

**Авторизация и конфигурация**

- Native flow явно маршрутизирует PAT, Session и OAuth без fallback.
  [`config_flow.py:51`](../../custom_components/time_messenger/config_flow.py#L51)

- Session flow удаляет неиспользованный remote session при незавершённой настройке.
  [`config_flow.py:105`](../../custom_components/time_messenger/config_flow.py#L105)

- Immutable unique ID обеспечивает изоляцию `(tenant origin, user_id)`.
  [`config_flow.py:216`](../../custom_components/time_messenger/config_flow.py#L216)

**Regression coverage и окружение**

- Реальный WS→pipeline→event тест защищает главную пользовательскую цепочку.
  [`test_api.py:454`](../../tests/components/time_messenger/test_api.py#L454)

- Handshake classification тестирует recovery для 401, 403, 429 и 5xx.
  [`test_api.py:404`](../../tests/components/time_messenger/test_api.py#L404)

- Dedupe restart-тест подтверждает подавление replay после перезапуска.
  [`test_dedupe.py:25`](../../tests/components/time_messenger/test_dedupe.py#L25)

- Dependency lock фиксирует Home Assistant 2026.8.1 и Python 3.14.
  [`pyproject.toml:1`](../../pyproject.toml#L1)
