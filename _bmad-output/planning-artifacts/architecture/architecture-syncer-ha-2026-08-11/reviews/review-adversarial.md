# Adversarial divergence review — ARCHITECTURE-SPINE

## Verdict

**Changes required.** Spine задаёт правильные крупные границы, но ещё не является достаточным build-substrate для независимо создаваемых модулей. Ниже приведены пары реализаций, которые могут честно считать себя совместимыми со всеми AD, однако расходятся на security- и data-integrity-критичных стыках. Наиболее опасные зоны: canonical tenant boundary и redirects, ownership OAuth/PAT/session secrets, multi-tenant OAuth namespace, реальная атомарность dedupe, privacy публичного HA event и lifecycle WebSocket при unload/reauth.

## Findings — adversarial divergence lens

### A1 — Tenant origin не задаёт security boundary

- **location:** AD-2, AD-4, AD-11; Consistency Conventions / Config
- **trigger_condition:** `normalized_tenant_origin` упомянут, но алгоритм normalization и допустимые адреса/redirects не определены.
- **divergent compliant units:** Реализация A считает `https://time.example`, `https://time.example:443/` и Unicode/IDNA-варианты одним origin и запрещает redirects. Реализация B сохраняет введённую строку, следует `30x` и повторно прикладывает Authorization после redirect. Обе выполняют «нормализует HTTPS origin» и используют TLS.
- **guard_snippet:** Определить origin как canonical tuple `(scheme=https, IDNA A-label host, effective port)`, запретить userinfo/query/fragment и non-root base path, задать политику IP/private-network targets, полностью отключить redirects для auth/API/WS либо разрешать только same-origin с повторной проверкой. `unique_id` строить из canonical tuple, а не display URL.
- **potential_consequence:** Дубли ConfigEntry, SSRF к внутренним HTTPS-сервисам и утечка bearer через redirect на другой origin.

### A2 — Ownership и persistence secrets остаются неоднозначными

- **location:** AD-3; Consistency Conventions / Config, Secrets; Structural Seed
- **trigger_condition:** PAT и session Token «сохраняются», OAuth использует Application Credentials, но не определено, какой storage владеет client secret, access token, refresh token и метаданными expiry для каждого mode.
- **divergent compliant units:** Реализация A хранит OAuth client secret глобально в HA Application Credentials, refresh/access tokens per entry и PAT/session token в `ConfigEntry.data`. Реализация B копирует client secret и все tokens в каждый ConfigEntry или держит access token только в runtime. Обе могут заявить соблюдение AD-3 и таблицы Config.
- **guard_snippet:** Добавить normative secret ownership matrix: secret → owner/store → persistence → redaction → rotation/removal lifecycle. Запретить копирование application client secret в ConfigEntry; определить, какие OAuth token fields принадлежат entry, и что удаляется при entry removal/reconfigure.
- **potential_consequence:** Секреты остаются после удаления entry, теряются после restart либо неожиданно попадают в backup/diagnostics; ротация одного credential ломает или не обновляет часть entries.

### A3 — Multi-tenant OAuth credentials не имеют однозначного namespace

- **location:** AD-2, AD-3; Structural Seed / `application_credentials.py`; Deferred / OAuth tenant details
- **trigger_condition:** OAuth endpoints названы tenant-derived, а Home Assistant Application Credentials обычно выбираются в integration domain, но ключ выбора credentials для нескольких tenant origins не задан.
- **divergent compliant units:** Реализация A разрешает одну глобальную пару `client_id/client_secret` для domain и подставляет endpoints текущего tenant. Реализация B регистрирует credentials отдельно по `(tenant_origin, client_id)`. При двух entries для разных tenants первый вариант может отправить client secret одному tenant к token endpoint другого.
- **guard_snippet:** Зафиксировать credential identity и lookup key как минимум `(canonical_tenant_origin, client_id)`, запретить cross-origin credential reuse без явного подтверждения, связать authorization/token endpoints и credential record одним immutable tenant descriptor.
- **potential_consequence:** Cross-tenant credential disclosure, невозможность настроить два tenants с разными OAuth clients и обновление неправильной учётной записи.

### A4 — OAuth transaction binding и refresh concurrency отложены за границу безопасной реализации

- **location:** AD-3, AD-9; Deferred / OAuth tenant details
- **trigger_condition:** Требуются authorization code и refresh, но обязательные `state`, PKCE, binding flow→entry→tenant, expiry skew и single-flight refresh не определены; PKCE оставлен как tenant detail.
- **divergent compliant units:** Реализация A использует state, PKCE S256, одноразовый flow context и один refresh под lock. Реализация B проверяет только возвращённый code и допускает параллельный refresh из REST и WebSocket supervisor. Обе не используют implicit grant и формально выполняют AD-3.
- **guard_snippet:** Сделать `state` и одноразовое binding к `(flow_id, canonical_origin, credential_id)` обязательными; установить PKCE policy; определить per-entry single-flight refresh, expiry skew, atomic replacement пары access/refresh token и поведение при rotated refresh token.
- **potential_consequence:** Login CSRF/tenant mix-up, повторное использование authorization response и инвалидирование rotating refresh token конкурентными запросами.

### A5 — `TokenProvider` не является достаточным межмодульным контрактом

- **location:** AD-3, AD-5, AD-9; Design Paradigm
- **trigger_condition:** Порт «выдаёт bearer», но не задаёт result type, expiry, refresh ownership, concurrency, invalidation и различие terminal/transient failure.
- **divergent compliant units:** REST client A запрашивает token перед каждым вызовом и Provider сам refresh-ит. WebSocket client B кэширует строку до disconnect и самостоятельно вызывает refresh. При ротации один продолжит пользоваться старым bearer; оба зависят от единого порта.
- **guard_snippet:** Специфицировать async protocol: `get_valid_token(min_ttl)`, `invalidate(observed_token, reason)`, immutable token generation/version, single-flight refresh и typed outcomes. Только Provider читает/пишет persistent token state; consumers не refresh-ят и не держат token дольше своей операции/connection generation.
- **potential_consequence:** Reauth storms, использование отозванного token, race при rotation и расхождение REST/WS identity.

### A6 — Уничтожение password/MFA сформулировано как недостижимая гарантия

- **location:** AD-3 / Session adapter
- **trigger_condition:** «password/MFA уничтожает после запроса» допускает трактовку как memory zeroization, которую нельзя надёжно гарантировать для Python strings и копий внутри HTTP stack.
- **divergent compliant units:** Реализация A лишь не сохраняет поля и освобождает references. Реализация B пытается занулять локальный buffer, хотя immutable copies остаются. Обе считают секрет «уничтоженным», но дают разную фактическую гарантию.
- **guard_snippet:** Заменить на проверяемый контракт: password/MFA никогда не пишутся в ConfigEntry/Store/logs/exceptions/diagnostics, не сохраняются после завершения flow и references удаляются в `finally`; явно не обещать process-memory zeroization.
- **potential_consequence:** Ложное security assurance и случайная persistence credentials через flow context, exception repr или debug capture.

### A7 — WebSocket generation и unload/reauth race не закрыты

- **location:** AD-5; state diagram; Consistency Conventions / Async
- **trigger_condition:** Требуются одна task и закрытие при unload, но не определены generation fencing, порядок cancel→close→await и запрет late reconnect/publish после unload или начала reauth.
- **divergent compliant units:** Реализация A отменяет supervisor, ждёт termination и только потом очищает runtime. Реализация B вызывает socket close, удаляет runtime_data, а уже запланированный retry создаёт новую connection; в каждый момент она всё ещё может считать, что владеет одной task.
- **guard_snippet:** Ввести per-entry lifecycle generation/cancellation token; каждый connect, receive и publish проверяет active generation. Нормативный unload: mark stopping → cancel timers/task → close socket → await task → flush/close storage → clear runtime. Reauth сначала fencing-ит текущую generation.
- **potential_consequence:** Zombie listener, события после disable/unload, двойной listener после reload и использование старого token после reauth.

### A8 — Handshake, liveness и resource limits WebSocket недоспецифицированы

- **location:** AD-4, AD-5, AD-11; `api/websocket.py`
- **trigger_condition:** «аутентифицированный websocket до hello» не выбирает header vs authentication challenge, timeout, ping/pong, max frame/message size, compression, receive queue или close-code mapping.
- **divergent compliant units:** Реализация A передаёт Authorization в handshake и ограничивает frame size. Реализация B сначала открывает anonymous socket, отправляет challenge без timeout и принимает unbounded compressed frames. Обе получают `hello` и используют HA aiohttp.
- **guard_snippet:** Задать один основной handshake algorithm и явно перечисленные fallback capability; установить connect/auth/hello/read-idle timeouts, heartbeat, maximum frame/decompressed payload, bounded receive queue, compression policy и close-code classification.
- **potential_consequence:** Tenant-specific incompatibility, зависшая setup task, memory/CPU exhaustion и бесконечный reconnect на terminal protocol error.

### A9 — Backoff можно обнулить атакуемым `hello`

- **location:** AD-5
- **trigger_condition:** Любой успешный `hello` немедленно сбрасывает backoff, даже если connection закрывается сразу после него.
- **divergent compliant units:** Реализация A трактует hello как успех и reconnect-ит почти без задержки после серии `hello`→close. Реализация B сбрасывает backoff лишь после stability window. Первая дословно соблюдает AD-5, вторая лучше защищает runtime, но уже расходится с ним.
- **guard_snippet:** Сбрасывать backoff после `hello` плюс заданного stable interval либо после обработки N валидных frames; rapid post-hello disconnect должен продолжать текущую attempt sequence. Задать максимальную частоту reconnect независимо от server behavior.
- **potential_consequence:** Tight reconnect loop, нагрузка на tenant и HA, rate-limit/ban и шум Repair/reauth.

### A10 — Нет bounded ordering/backpressure contract между listener и Store

- **location:** AD-1, AD-5, AD-7; Design Paradigm
- **trigger_condition:** Не определено, listener ждёт pipeline последовательно, создаёт task на frame или кладёт frames в очередь; Store I/O находится в критическом пути каждого сообщения.
- **divergent compliant units:** Реализация A последовательно await-ит check/save/fire и создаёт server-side backlog. Реализация B создаёт unbounded task на каждый event, допускает reorder и истощает память. Обе имеют один WebSocket и per-entry dedupe lock.
- **guard_snippet:** Определить bounded per-entry FIFO queue, одного consumer, предел ёмкости и explicit overflow policy. Запретить fire-and-forget tasks per frame; задать telemetry/Repair при overflow и сохранить ordering как минимум по receive sequence.
- **potential_consequence:** Потеря/reorder сообщений, memory exhaustion и непредсказуемая задержка при burst или медленном Store.

### A11 — Источник истины для `D` classification не определён

- **location:** AD-6; `api/client.py` channel cache
- **trigger_condition:** Тип канала разрешено брать «из payload либо REST-backed cache», но нет precedence, validation или invalidation rule при их расхождении.
- **divergent compliant units:** Реализация A доверяет payload `channel_type=D`, даже если cache говорит `G`. Реализация B доверяет cache, даже если он устарел после channel conversion. Обе defensively декодируют и используют один из разрешённых AD-6 источников.
- **guard_snippet:** Установить authoritative precedence: при отсутствии или конфликте выполнить same-origin REST lookup; публиковать только после подтверждённого `D`. Описать TTL/invalidation по channel events и negative cache. Любой conflict — protocol/security telemetry без message text.
- **potential_consequence:** Текст группового/private канала ошибочно публикуется как direct message в HA event bus либо валидные DM молча теряются.

### A12 — Dedupe `save before fire` не задаёт crash-consistency и delivery semantics

- **location:** AD-7
- **trigger_condition:** «сохраняет state через Home Assistant Store до async_fire» не определяет, когда запись считается durable, что делать при fire exception и какую гарантию даёт система: at-most-once или at-least-once.
- **divergent compliant units:** Реализация A считает завершение `Store.async_save` durable и навсегда оставляет mark при ошибке publisher. Реализация B откатывает mark после fire error и повторяет message после reconnect. Обе выполняют check-and-mark до вызова `async_fire`, но одна теряет событие, другая допускает дубль.
- **guard_snippet:** Явно выбрать delivery contract. Для выбранного at-most-once: commit dedupe record до fire, fire не должен быть retried, store API должен иметь подтверждённую completion semantics, а crash window документируется. Для stronger guarantee нужен journal/outbox state machine (`prepared`/`published`) с deterministic recovery; простой set недостаточен.
- **potential_consequence:** Необнаружимая потеря личного сообщения либо повторный HA event после restart/error при том, что CAP-4 обещает отсутствие дублей.

### A13 — Dedupe retention и eviction не детерминированы

- **location:** AD-7; Consistency Conventions / IDs и время
- **trigger_condition:** «5000 новейших ID и не дольше 24 часов» не говорит, что значит newest/age: Time `created_at`, receive time, commit time или order в container; не задано поведение при clock skew и delayed replay.
- **divergent compliant units:** Реализация A сортирует по remote `created_at`, B — по local first-seen, C — по insertion order загруженного dict. При старом replay A немедленно удалит mark и допустит повтор, B удержит его 24 часа; все соблюдают численные лимиты.
- **guard_snippet:** Хранить record `{post_id, first_seen_utc, receive_sequence}`; TTL считать от successful local mark с задокументированной clock policy, cap применять детерминированно по receive sequence. Валидировать Store schema/version и атомарно мигрировать corrupted/old state fail-closed или через Repair.
- **potential_consequence:** Дубли после reconnect, различные результаты после restart и бесконтрольное отбрасывание валидных сообщений при clock anomalies.

### A14 — State изолирован по `entry_id`, а identity — по другому ключу

- **location:** AD-2, AD-7
- **trigger_condition:** Уникальность задаётся `(tenant_origin, time_user_id)`, но dedupe namespace — `entry_id`; remove/re-add, reauth identity mismatch и reconfigure origin не имеют migration/fencing rule.
- **divergent compliant units:** Реализация A удаляет Store вместе с entry и после re-add повторно публикует replay. Реализация B сохраняет Store по hash identity и наследует marks. Обе изолируют текущие entries и не смешивают state между одновременными runtimes.
- **guard_snippet:** Определить lifecycle state key и migration policy. Запретить изменение canonical origin/user_id in place без revalidation; при reauth другой `user_id` прекращать setup и требовать new entry. Явно решить, должна ли dedupe continuity переживать remove/re-add, и тестировать выбранный contract.
- **potential_consequence:** Повторные события после reconfiguration либо, хуже, suppress сообщений нового пользователя state-ом предыдущего.

### A15 — Mandatory `message_text` создаёт неразрешённую privacy divergence

- **location:** AD-8; Consistency Conventions / Config, Secrets; Deferred / EventEntity
- **trigger_condition:** Raw personal message text обязателен в глобальном HA event, но `text_redacted` лишь optional и privacy options не определены: default, режимы, truncation, attachments, control characters и доступ diagnostics/logbook не заданы.
- **divergent compliant units:** Реализация A всегда публикует полный `message_text`; B по privacy option публикует `""` и `text_redacted=true`; C маскирует шаблоны secrets. Все сохраняют обязательное поле и не публикуют raw Time payload/secrets, но автоматизации получают несовместимое содержание.
- **guard_snippet:** Задать privacy contract и безопасный default: например `metadata_only` по умолчанию, explicit opt-in для full text; `message_text` semantics для redacted mode, maximum UTF-8 length, normalization/control-character handling, policy для `file_ids`/sender fields и гарантию, что telemetry никогда не содержит content. Документировать, кто в HA имеет доступ к bus events.
- **potential_consequence:** Утечка личной переписки в automation traces, logs или сторонние integrations либо молчаливо пустой текст, ломающий consumers.

### A16 — Event schema перечисляет поля, но не определяет wire-level contract

- **location:** AD-8; Consistency Conventions / Event evolution
- **trigger_condition:** Нет типов, nullability, length bounds, exact timestamp grammar, semantics `text_redacted`, ordering `file_ids`, duplicate handling и machine-readable validator. «Additive optional» не гарантирует, что consumers игнорируют неизвестные поля.
- **divergent compliant units:** Один publisher выдаёт `schema_version` integer, `created_at` с `Z`, `file_ids=[]`; другой — string version, `+00:00`, отсутствующий `file_ids`. Оба могут считать поля плоскими и схему version 1.
- **guard_snippet:** Добавить normative JSON Schema/TypedDict с exact types, required/optional/null rules, RFC 3339 UTC representation, size bounds и examples; publisher валидирует до `async_fire`. Уточнить forward-compatibility rule для consumers и migration-window duration/dual-publish behavior.
- **potential_consequence:** Независимо созданные automations несовместимы, malformed payload проходит в event bus, а schema v1 перестаёт быть стабильным контрактом.

### A17 — Failure taxonomy неполна и допускает противоположные state transitions

- **location:** AD-9; state diagram
- **trigger_condition:** Нет нормативного mapping для `403`, `404`, TLS validation, cross-origin redirect, WS close codes, auth challenge rejection, JSON/schema error, Store corruption/full disk и repeated malformed events.
- **divergent compliant units:** Реализация A трактует 403 как reauth, B как unsupported capability/Repair, C как transient retry. Все используют перечисленные exception classes, но пользователь и server получают совершенно разное поведение.
- **guard_snippet:** Добавить exhaustive failure decision table: source/status/close code → normalized error → retry budget/backoff → lifecycle state → user-visible Repair/reauth → logging redaction. Unknown protocol/security failures должны быть terminal fail-closed до явного reload, не generic transient.
- **potential_consequence:** Бесконечные retry storms, запрос пользователю переавторизоваться при нехватке прав, скрытая data loss при storage failure и token use после terminal rejection.

### A18 — Multi-entry UI/Repair/reauth isolation не закреплена контрактом

- **location:** AD-2, AD-5, AD-9; state diagram
- **trigger_condition:** Runtime/state объявлены per-entry, но Repair issue ID, reauth flow selection, application credential rotation и service/event routing при нескольких entries не имеют entry-scoped keys.
- **divergent compliant units:** Реализация A создаёт issue `unsupported_capability` на integration domain и один reauth flow; entry B перезаписывает issue/flow entry A. Реализация B включает `entry_id` в issue and flow keys. Обе держат runtime_data отдельно.
- **guard_snippet:** Все issues, reauth flows, timers, telemetry counters и token invalidation key-ить canonical entry identity/entry_id; flow result обязан подтвердить исходные origin и user identity. Global application credential update должен fan-out только entries, которые ссылаются на тот же credential record.
- **potential_consequence:** Починка одного tenant скрывает проблему другого, credentials применяются не к той учётной записи, а UI сообщает ложное healthy state.

### A19 — Acceptance gate не производит воспроизводимое доказательство

- **location:** AD-12; `scripts/probe_time_tenant.py`; Stack
- **trigger_condition:** Не определены probe artifact, привязка результата к origin/server build/auth mode, срок действия и критерии pass/fail для replay/self/G/P/O; «release gate» может означать разное для разработчика и CI/release owner.
- **divergent compliant units:** Реализация A запускает probe вручную один раз и сохраняет устный результат. Реализация B генерирует подписанный/redacted JSON matrix на каждый server build. Обе могут заявить, что probe подтвердил список случаев.
- **guard_snippet:** Определить versioned redacted result schema с canonical origin hash, server_version/build, integration version/commit, auth mode, timestamp и результатом каждого сценария; задать freshness/re-run triggers и запретить message/token material в artifact.
- **potential_consequence:** Поддержка заявляется для другого build/tenant, регрессии проходят release gate, а sensitive probe payload попадает в CI artifact.

## Exit conditions for build-substrate

Spine станет пригодным для независимой реализации после появления следующих normative contracts:

1. Canonical tenant descriptor и redirect/network boundary.
2. Secret ownership matrix и полный async `TokenProvider` lifecycle, включая multi-tenant OAuth transaction/refresh rules.
3. WebSocket generation, handshake, resource limits, backpressure и exhaustive failure/state table.
4. Выбранная delivery guarantee с доказанной Store/journal atomicity, deterministic retention и state lifecycle across reconfigure/remove/re-add.
5. Machine-readable HA event schema с explicit privacy modes/defaults и multi-entry scoped UI/Repair identifiers.

