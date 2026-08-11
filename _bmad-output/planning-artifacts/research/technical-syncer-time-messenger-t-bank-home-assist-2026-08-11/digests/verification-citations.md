# Semantic citation verification

Проверены load-bearing утверждения резюме, архитектурной рекомендации и раздела рисков. Использовано 10 source opens; приоритет отдан официальным страницам Time/T‑Bank и Home Assistant. Итог: **есть один материальный partial mismatch**, который не опровергает общую техническую реализуемость, но завышает доказанность главного deployment blocker. Есть также один нематериальный wording gap.

## Проблемы

### 1. Отключаемость ботов и зависимость от лицензии не подтверждены marker [6]

- **Цитата / секция:** Резюме — «администратор может отключить webhooks, ботов, персональные токены или OAuth»; §4.1 — «Публичная документация не гарантирует, что webhooks, bots, OAuth и PAT включены в конкретной лицензии или tenant. [6]»
- **Marker:** [6], официальная страница «Управление интеграциями».
- **Mismatch:** страница прямо документирует enable/disable для incoming webhooks, outgoing webhooks, пользовательских slash-команд, OAuth provider и PAT. На ней нет настройки отключения bot accounts и нет матрицы доступности этих функций по лицензиям. Следовательно, marker [6] поддерживает tenant/configuration gating перечисленных интеграций, но не две более сильные части утверждения: «ботов можно отключить» и «функции могут отсутствовать в конкретной лицензии».
- **Предлагаемая correction:** «Администратор может отключить incoming/outgoing webhooks, пользовательские slash-команды, PAT или OAuth; возможность создания ботов, роли/права и лицензионные ограничения нужно отдельно проверить на целевом tenant». Если отдельного официального источника о bot/license gating нет, убрать «ботов» из списка документированных feature flags и заменить «лицензии или tenant» на «конфигурации tenant».
- **Материальность:** да. Рекомендуемый production spine зависит от bot account, поэтому различие между документированным feature flag и неподтверждённым предположением должно быть видимо читателю.

### 2. «Отложенный ответ» slash-команды сильнее текста marker [9]

- **Цитата / секция:** §2, матрица — «синхронный или отложенный ответ»; §3, capability probe — проверка `timeout` и `response_url`.
- **Marker:** [9], официальный cookbook slash-команд.
- **Mismatch:** источник документирует выдаваемый токен, поля request payload, наличие `response_url` и структуру ответа, но на просмотренной странице не формулирует гарантированный asynchronous/deferred callback contract, его timeout или retry semantics. Наличие поля `response_url` делает deferred flow правдоподобным, но само по себе не доказывает его эксплуатационный контракт.
- **Предлагаемый downgrade:** «синхронный ответ; payload содержит `response_url`, возможность и сроки отложенного ответа проверить на tenant». Текущий capability probe уже корректно предусматривает эту проверку.
- **Материальность:** нет; это уточнение границы контракта, а не опровержение выбора slash-команды.

## Подтверждённые load-bearing claims

- **[6]** подтверждает создание incoming webhook URL для публичных и private-каналов, trigger-word outgoing webhooks только для публичных каналов, а также административные переключатели webhooks, slash-команд, OAuth и PAT.
- **[7]** подтверждает отправку одним `POST /api/v4/posts` с `Authorization: Bearer <bot token>`; приведён пример direct peer через `peer: "@yoona"`. Утверждение об отправке ботом личного сообщения поддержано. Более широкую адресацию каналов лучше считать ожидаемой, но проверять capability probe.
- **[8]** подтверждает `/api/v4/websocket`, аутентификацию cookie/Authorization/authentication challenge, событие `hello` с server version и события `posted`, `post_edited`, `post_deleted`, reactions и status changes. Рекомендация REST + authenticated WebSocket имеет прямую опору.
- **[9]** подтверждает статически выдаваемый token для валидации slash request и поля `team_id`, `channel_id`, `response_url`; рекомендация проверять token и allowlist IDs поддержана.
- **[10]** подтверждает существование опубликованного API version 5.0 параллельно разделу v4.
- **[1], [11], [12]** подтверждают, соответственно, исключительное право ООО «ТЦР» на «Корпоративный мессенджер Time» (реестровая запись № 28364), листинг Syncer от Arctera AM и отдельный листинг Time. Разные Android IDs видны в URL листингов. Эти источники не устанавливают связь Syncer ↔ Time, поэтому отчёт корректно не выводит такую связь из storefront data.
- **[14]** подтверждает Home Assistant `rest_command` с POST, headers, templated payload, JSON content type, `verify_ssl`, secret authorization header и `response_variable`.
- **[15]** подтверждает, что HA webhook не требует иной аутентификации, кроме знания `webhook_id`, по умолчанию local-only, для прямого интернет-доступа нужен `local_only: false`, и его нельзя использовать для destructive/safety-sensitive действий.

## Корректно обозначенные inference / limited negative findings

- «Не найдена единая migration/deprecation/parity matrix v4↔v5» корректно названо результатом ограниченного поиска, а не доказательством отсутствия документа. Marker [10] доказывает только наличие v5; отчёт эту границу соблюдает.
- Отсутствие исчерпывающих retry/replay/ordering guarantees корректно ограничено формулировкой «на просмотренных страницах». Это допустимый negative finding, а reconnect/dedupe/REST-resync явно поданы как defensive architecture inference.
- Вывод, что разные application ID доказывают только разные мобильные листинги, но не общую/разную кодовую базу, backend или договорные отношения, сформулирован корректно и осторожно.
- Вывод «интеграционной поверхностью должен быть сервер Time, а не мобильный клиент» является архитектурной inference. Он разумен при принятом пользовательском контексте, но зависимость Syncer от Time всё равно правильно вынесена в capability/admin verification.

## Вердикт

**Material mismatch: yes, limited.** Marker [6] не поддерживает заявленную отключаемость ботов и лицензионный gating. После сужения этой формулировки основное заключение — capability prototype, затем bot REST + authenticated WebSocket, slash-команда для явных входящих действий и HA `rest_command`/incoming webhook для MVP — остаётся семантически поддержанным проверенными официальными источниками.
