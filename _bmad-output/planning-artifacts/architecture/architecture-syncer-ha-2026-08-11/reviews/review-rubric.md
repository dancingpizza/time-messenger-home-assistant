# Reviewer Gate — rubric walker и сверка входов

**Объект:** `ARCHITECTURE-SPINE.md`  
**Входы для сверки:** `SPEC.md`, `authentication-methods.md`  
**Дата проверки:** 2026-08-11

## Вердикт

**Не проходит gate без доработки.** Spine хорошо фиксирует границы, владельцев state, event contract, транспорт и operational envelope, а механический lint чист; однако текущий контракт не разрешает privacy-выбор из SPEC, опускает обязательный lifecycle удаления credentials и заявляет более сильную семантику доставки, чем обеспечивает порядок `Store → async_fire`.

## Детерминированная проверка

`lint_spine.py --workspace …/architecture-syncer-ha-2026-08-11` завершился с `ok: true`, `total_findings: 0`.

Нет placeholders, дублированных AD ID, пропущенных `Binds` / `Prevents` / `Rule` или незакреплённых версий stack.

## Good-spine checklist

| Критерий | Результат | Обоснование |
| --- | --- | --- |
| Фиксирует реальные точки расхождения уровня реализации и не пропускает их | **Частично** | Хорошо зафиксированы auth adapters, identity ownership, WebSocket lifecycle, filtering, dedupe ownership и HA event schema. Не зафиксированы privacy-режим публичного события и lifecycle удаления auth/dedupe state. |
| Каждый Rule исполним и предотвращает заявленное расхождение | **Частично** | Большинство Rule проверяемы кодом или acceptance probe. AD-7 предотвращает дубли, но не гарантирует заявленное «ровно одно событие» при сбое между сохранением ID и публикацией. AD-5 называет алгоритм backoff, но оставляет его числовой контракт свободным. |
| В Deferred нет решения, способного вызвать несовместимость двух нижележащих units | **Проходит с оговоркой** | Backfill, расширение типов чатов, UI/platforms и distribution действительно можно отложить. OAuth tenant details имеют явный revisit condition; privacy ошибочно не находится ни в Deferred, ни в assumption. |
| Именованные технологии актуальны и reality-checked | **Проходит** | Официальный `home-assistant/core` `2026.8.1` подтверждает Python `>=3.14.2` и `aiohttp==3.14.3`; официальные Time docs подтверждают `/api/v4/users/login`, Bearer `Token`, `/api/v4/websocket`, `hello`, Authorization Code и refresh. |
| Не противоречит существующему brownfield-коду | **Неприменимо** | Представлен greenfield structural seed; существующая реализация в объём проверки не входила. |
| Покрывает capabilities исходной SPEC | **Частично** | CAP-1–CAP-6 имеют явную карту и в основном покрыты. Privacy open question принят как безусловный raw-text contract, а exactly-once формулировка не согласована с фактической семантикой AD-7. |
| Не ослабляет inherited parent spine | **Неприменимо** | Parent spine не указан. |
| Каждое измерение altitude решено, отложено или вынесено в open question | **Проходит** | Dependency/state ownership, transport, auth, schema evolution, security, deployment/runtime, failure handling и release acceptance присутствуют; distribution/CI явно Deferred. |

## Сверка с SPEC и authentication-methods

| Входной контракт | Где отражён | Итог |
| --- | --- | --- |
| CAP-1: OAuth, PAT, session token, identity check, без hidden fallback | AD-2–AD-4, AD-9, auth adapters | Покрыто. Выбор session acquisition через документированный `/api/v4/users/login` допустим формулировкой «получить либо принять» companion-файла; SSO-only явно Deferred. |
| CAP-2: WebSocket как основной transport | AD-4–AD-6, AD-10–AD-12 | Покрыто. |
| CAP-3: только чужие личные сообщения | AD-6 | Покрыто как `[ASSUMPTION]`: только `D`, остальные типы fail-closed / Deferred. |
| CAP-4: дедупликация через restart в согласованном окне | AD-7 | Частично: окно и durable state заданы, но порядок mark-before-publish создаёт окно потери и не даёт exactly-once. |
| CAP-5: единое расширяемое HA event | AD-8 и conventions | Схема покрыта, но режим раскрытия текста не согласован с privacy open question. |
| CAP-6: reconnect с ограниченной задержкой и без дублей | AD-5, AD-7, AD-9 | Частично: класс backoff задан, числовая верхняя граница и reset stability не закреплены. Gap-free recovery честно Deferred и не требуется CAP-6. |
| Удаление конфигурации очищает локальные токены; remote revoke только при поддержке | — | Не покрыто. Unload в AD-5 не эквивалентен remove и не определяет очистку auth data / dedupe Store. |
| Секреты не попадают в events/logs/diagnostics | AD-8, AD-9, Secrets convention | Покрыто. |
| Недоступный auth mode показывается как unsupported | AD-12 | Покрыто. |

## Findings

### HIGH-1 — AD-8 без решения пользователя превращает privacy open question в обязательную публикацию полного текста

- **Evidence:** SPEC оставляет открытым, допустимы ли полный текст, Logbook, masking и opt-in. AD-8 без `[ASSUMPTION]` делает `message_text` обязательным полем публичного `time_messenger_event`, а `text_redacted` — лишь необязательным флагом без семантики.
- **Почему это hole:** два publisher могут полностью соответствовать AD-8, но один передавать raw text, другой маскированный текст; automation consumers получат несовместимый контракт. Кроме того, решение расширяет поверхность раскрытия личных сообщений до принятия privacy-политики.
- **Действие:** **discuss.** Либо получить явное решение и пометить AD-8 `[ADOPTED]`, либо сохранить `[ASSUMPTION]` и добавить revisit condition. Rule должен однозначно определить default, opt-in/opt-out, значение `text_redacted`, содержимое `message_text` при masking и ожидаемое поведение traces/Logbook.

### HIGH-2 — AD-7 обеспечивает at-most-once, но не «ровно одно событие» из success signal

- **Evidence:** AD-7 сначала сохраняет `post_id` в `Store`, затем вызывает `async_fire`; при остановке процесса между этими действиями повторная доставка будет подавлена. SPEC требует, чтобы новое сообщение создавало ровно одно событие, а повторная доставка не создавала второе.
- **Почему это hole:** `Store` и in-memory HA event bus не образуют одной транзакции. Текущий Rule осознанно выбирает отсутствие дублей ценой возможной потери, но spine не фиксирует этот trade-off и формально обещает больше, чем может исполнить.
- **Действие:** **discuss.** Согласовать контракт как at-most-once в пределах dedupe-window и поправить success signal либо ввести отдельную persisted pending/outbox-модель с явно описанной остаточной crash-семантикой. Не использовать термин exactly-once без доказуемой атомарной границы.

### HIGH-3 — Обязательный removal/revoke lifecycle из authentication-methods нигде не закреплён

- **Evidence:** `authentication-methods.md` требует удалять локальные токены при удалении конфигурации и выполнять remote revoke только когда протокол и сервер его поддерживают. Spine описывает unload listener, reauth и secret redaction, но не removal.
- **Почему это hole:** независимо реализованные config-flow и auth adapter могут по-разному трактовать удаление: оставить per-entry `Store`, не попытаться revoke OAuth/PAT или смешать временный unload с окончательным remove. Это security- и ownership-расхождение.
- **Действие:** **autofix.** Дополнить AD-2/AD-3 либо добавить AD: `ConfigEntry` владеет auth data и dedupe Store; remove очищает всё локальное per-entry состояние; remote revoke вызывается только при документированной поддержке выбранного mode; отсутствие revoke или его ошибка не сохраняют локальные secrets. Развести unload и remove отдельными правилами.

### MEDIUM-1 — AD-5 не полностью предотвращает заявленное расхождение retry-политик

- **Evidence:** Rule требует `capped exponential full-jitter backoff`, но не задаёт initial delay, cap, критерий стабильного соединения перед reset и поведение при server-provided retry hint. AD-9 отдельно определяет `Retry-After` только для HTTP `429`.
- **Почему это hole:** runtime supervisor и WebSocket adapter могут выбрать существенно разные задержки и оба формально выполнить AD-5; требование CAP-6 «с ограниченной задержкой» останется непроверяемым.
- **Действие:** **autofix после выбора чисел.** Закрепить один набор constants и тестируемые переходы либо назначить единственного владельца policy (`runtime.py`) и запретить adapter-level sleep/retry. Если числа должны остаться implementation-owned, убрать из `Prevents` обещание предотвращать несовместимые retry-политики.

## Что проходит без замечаний

- AD-1 и structural seed дают ясное направление зависимостей и единственный composition root.
- AD-2 явно закрепляет identity и persistent/runtime ownership на ConfigEntry.
- AD-4, AD-6, AD-9–AD-12 согласуют capability gating, fail-closed filtering, error taxonomy, API isolation, TLS/runtime boundary и tenant acceptance.
- AD-8 хорошо фиксирует имя события, версию, обязательные поля и правила additive evolution; замечание относится только к privacy-семантике текста.
- Current-version claims подтверждены первичными источниками: [Home Assistant Core 2026.8.1 `pyproject.toml`](https://raw.githubusercontent.com/home-assistant/core/2026.8.1/pyproject.toml), [Time API authentication](https://docs.time-messenger.ru/api/v4/%D0%B0%D1%83%D1%82%D0%B5%D0%BD%D1%82%D0%B8%D1%84%D0%B8%D0%BA%D0%B0%D1%86%D0%B8%D1%8F/), [Time WebSocket](https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/), [Time OAuth2 provider](https://docs.time-messenger.ru/integrations/oauth2_service_provider/).

