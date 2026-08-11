---
title: "Пользовательский опыт документации Time Messenger integration"
name: "Time Messenger for Home Assistant Docs"
status: final
created: 2026-08-11
updated: 2026-08-11
sources:
  - ../../../specs/spec-hacs-documentation-branding/SPEC.md
  - ../../../specs/spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md
  - ../../../specs/spec-syncer-time-messenger-t-bank-home-assist/authentication-methods.md
  - ../../architecture/architecture-syncer-ha-2026-08-11/ARCHITECTURE-SPINE.md
  - ../../research/technical-syncer-time-messenger-t-bank-home-assist-2026-08-11/research.md
---

# Time Messenger for Home Assistant: Experience Spine

## Foundation

Основная поверхность: один responsive README для GitHub и HACS `render_readme`. Отдельного UI system нет. `DESIGN.md` задаёт визуальную идентичность и голос, а этот файл определяет порядок, поведение, состояния и задачи чтения.

Читатели уже умеют пользоваться Home Assistant, мотивированы и примерно понимают назначение integration. Документация не обучает основам HA и не дублирует архитектурные контракты. Русский является основным языком; English ограничен обязательным коротким summary.

### Обязательные границы продукта

- Integration принимает только новые чужие обычные сообщения из 1:1 каналов `D`.
- Каналы `G/P/O`, backfill, gap-free delivery и встроенные automation actions не входят в v0.0.1.
- Home Assistant `2026.8.1+`, Time API v4 и успешный acceptance probe целевого tenant обязательны.
- Пользователь выбирает OAuth, PAT или Session явно. Integration не меняет auth mode автоматически.
- `message_text` равен `null` по умолчанию. Secrets и raw payload не попадают в logs или diagnostics.

## Information Architecture

README остаётся одной страницей с якорями:

| Surface | Reached from | Purpose |
|---|---|---|
| Введение | Открытие README / HACS landing | Понять пользу, границы v0.0.1 и минимальную версию HA |
| Установка | Следующий блок / якорь | Установить через HACS; при необходимости найти manual recovery path |
| Авторизация | После установки | Выбрать разрешённый tenant policy способ и войти |
| Privacy и event schema | После входа / якорь | Понять privacy default и получить полный `time_messenger_event` schema v1 |
| Automation recipes | После schema / якорь | Создать notification, light blink или TTS как пользовательскую HA automation |
| Эксплуатация и помощь | Конец README / ошибка по пути | Найти reauth, reconnect, diagnostics, removal и issue tracker |

Порядок задач: оценка, установка, auth choice, schema, первая automation, восстановление или удаление. Первый экран не содержит auth, privacy или protocol wall.

## Voice and Tone

Brand voice и метафора живут в `DESIGN.md`. Здесь остаются только правила microcopy, от которых зависят выбор и восстановление после ошибки.

| Делать | Не делать |
|---|---|
| «Привет! Эта integration превращает личные сообщения Time в события Home Assistant.» | «Настоящая документация описывает архитектуру событийного pipeline…» |
| «Не пропускайте важное: покажите notification, мигните светом или озвучьте сообщение.» | «Интеграция поддерживает Алису, лампы и уведомления.» |
| «OAuth рекомендуется, если его настроила ваша организация.» | «Выберите любой удобный способ. Integration переключится сама.» |
| «Не удалось войти: этот способ может быть отключён политикой tenant.» | «Unknown authentication failure.» |
| Короткое действие, затем причина или ограничение | Длинные предупреждения до первого полезного шага |

Термины `integration`, `tenant`, `OAuth`, `PAT`, `Session`, `ConfigEntry`, `time_messenger_event` и `schema_version` пишутся буквально там, где важна техническая точность.

## Component Patterns

Behavioral contract; визуальные спецификации находятся в `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| `readme-intro` | Верх README | Даёт русское описание, короткий English summary и пометку о неофициальном статусе, после чего сразу ведёт к пользе и установке. |
| `use-case-teaser` | Первый экран | Ведёт к соответствующему `automation-recipe`. Называет результат, не выдавая recipe за встроенную функцию. |
| `compatibility-callout` | До установки | Останавливает установку, если версия Home Assistant ниже `2026.8.1`, и ведёт к полным ограничениям и tenant acceptance context. |
| `installation-sequence` | Установка | Сначала проводит через HACS custom repository `dancingpizza/time-messenger-home-assistant`, restart и config flow. Manual path раскрывается только как recovery и требует скопировать `custom_components/time_messenger`. |
| `auth-choice` | Авторизация | Сохраняет порядок OAuth, PAT, Session. Пользователь выбирает один mode; для каждого варианта указаны prerequisites, сохраняемые данные и результаты unsupported и reauth. Автоматического fallback нет. |
| `privacy-callout` | Перед event schema | До opt-in сообщает `message_text: null` и объясняет, что logs/diagnostics не содержат secrets или raw payload. |
| `event-schema` | Event contract | Даёт полный schema v1 и redacted example. При копировании сохраняются обязательные поля; `schema_version: 1` не смешивается с package version. |
| `automation-recipe` | Recipes | Даёт минимальный копируемый YAML и называет его пользовательской HA automation. Notification идёт первым, затем light blink и TTS. |
| `troubleshooting-item` | Эксплуатация | Начинается с наблюдаемого симптома и различает reauth, transient reconnect, unsupported tenant и known limitation. Не предлагает автоматическую смену auth mode. |
| `support-link` | Removal / support | Объясняет локальное удаление и best-effort logout для Session. Для issue просит только redacted diagnostics. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Cold read | Введение | Заголовок и первая секция объясняют пользу без обязательного оглавления |
| Установка заблокирована | Совместимость / установка | README останавливает читателя на несовместимой HA; при недоступном HACS раскрывает manual recovery |
| Auth недоступен | Авторизация | README помечает mode как unsupported и направляет к администратору, не переключая mode |
| Reauth или disconnect | Эксплуатация | Auth failure возвращает к тому же mode; для transient failure README объясняет reconnect без обещания gap-free delivery |
| Privacy default | Privacy / schema | README показывает `message_text: null` и `text_redacted: true` до примеров с текстом |
| Recipe не готов к запуску | Recipes | Читатель заменяет entity/service на существующие в своей HA; integration не создаёт устройство или service |
| Решение не найдено / removal | Помощь | README ведёт к redacted diagnostics и issue tracker либо к локальному удалению с best-effort Session logout |

GitHub и HACS управляют loading, offline и permission-denied состояниями самой страницы.

## Interaction Primitives

- Читатель движется по странице вертикальным scroll. Якорные ссылки ускоряют переход к установке, auth, schema, recipes и troubleshooting.
- Читатель копирует YAML и payload из fenced code blocks. Каждый пример полностью покрывает свою задачу.
- Внешние ссылки ясно называют назначение и не заменяют обязательную информацию внутри README.
- Критические compatibility, privacy и limitation facts остаются открытыми, а не прячутся в disclosure.
- README не использует hover-only affordances, карусели или автоматический выбор auth mode.

## Accessibility Floor

- Семантическая иерархия H1 → H2 → H3 без пропусков; один H1 на страницу.
- Motion отсутствует; изображения получают содержательный alt text, headings семантичны, code examples копируемы.
- Смысл предупреждения и статуса передаётся текстом, а не только цветом или emoji.
- Ссылки имеют различимый текст назначения; одинаковые подписи не ведут в разные места.
- Code blocks не содержат обязательную информацию, которой нет в окружающем объяснении; строки по возможности короткие, чтобы mobile reader не терял контекст.
- Клавиатурный фокус остаётся видимым, а визуальные комбинации соответствуют WCAG 2.2 AA согласно `DESIGN.md`.

## Responsive & Platform

Один Markdown одинаково читается в HACS, GitHub desktop и mobile. README использует одну колонку, короткие абзацы и не передаёт смысл только цветом. Широких таблиц в итоговом README нет. Desktop не получает отдельную композицию, а mobile сохраняет все шаги и caveats.

Семантика, ссылки, code blocks и фокус наследуются от Markdown renderer. При различиях между GitHub и HACS выбирается разметка, которая сохраняет смысл в обеих поверхностях. При конфликте с будущими mockups или imports приоритет имеют spines. Все поверхности остаются `spine-only`; native Markdown не требует visual reference.

## Definition of Done для README

- Секции идут в порядке source contract; первый экран остаётся коротким.
- Все installation, auth, privacy, schema, recipes, troubleshooting, removal и support facts сверены с источниками.
- Все code blocks и URLs точны и копируемы; recipes явно названы пользовательскими automation.
- Проверены mobile reading, heading hierarchy, alt text, links, WCAG 2.2 AA и отсутствие wide-table dependency.
- Humanizer Gate пройден; в repository попадает только финальный README.

### Humanizer Gate

После factual и structural checks редактор обязан вызвать skill `humanizer`. Процесс состоит из трёх артефактов: draft, still-AI audit и final. Редактор сохраняет все факты, code blocks и URLs. В final нет em dash или en dash, рекламного AI-языка, искусственного правила трёх, механических bold lists, title-case headings, декоративных emoji, filler, chatbot artifacts и generic conclusion.

В repository попадает только final README. Draft, still-AI audit и другая audit evidence относятся к implementation verification и не публикуются в пользовательской документации.

## Key Flows

По пользовательскому override все пять flows task-based, без вымышленного протагониста. `CAP-8` покрыт первым flow; `CAP-7`, `CAP-9` и `CAP-10` относятся к delivery и не создают читательской journey.

### CAP-8: оценить совместимость и назначение до установки

1. Читатель открывает README в GitHub или HACS.
2. `readme-intro` называет integration неофициальной и одной фразой объясняет связь Time → Home Assistant.
3. `use-case-teaser` показывает notification, light blink и TTS как примеры пользовательских automation.
4. Блок возможностей уточняет: v0.0.1 принимает только новые чужие обычные сообщения в 1:1 `D`; `G/P/O`, backfill и встроенные actions отсутствуют.
5. `compatibility-callout` показывает Home Assistant `2026.8.1+`, Time API v4 и необходимость проверки целевого tenant.
6. Кульминация: читатель может осознанно решить, подходит ли integration, не открывая исходный код.

Failure path: версия HA ниже минимальной или tenant не прошёл acceptance probe → установка не рекомендуется; README ведёт к compatibility/known limitations, не обещая обход.

### Установить integration

1. Читатель переходит к `installation-sequence` сразу после коротких тизеров и compatibility fact.
2. Добавляет custom repository `dancingpizza/time-messenger-home-assistant` через HACS My link или интерфейс HACS.
3. Устанавливает integration и перезапускает Home Assistant.
4. Открывает Settings → Devices & services и добавляет Time Messenger.
5. Кульминация: config flow открыт, integration готова к выбору auth mode.

Failure path: HACS недоступен → manual recovery subsection требует скопировать только `custom_components/time_messenger`, затем повторить restart и config flow.

### Выбрать и завершить авторизацию

1. После установки читатель открывает `auth-choice`.
2. Если организация настроила OAuth, выбирает его как рекомендуемый refreshable вариант без хранения пароля.
3. Если OAuth недоступен, а администратор разрешил personal tokens, выбирает PAT как простой самостоятельный способ.
4. Session выбирается только как fallback. Политика SSO может запрещать вход через API; integration сохраняет только session token.
5. После выбора integration выполняет identity check и обменивается WebSocket-сообщением `hello`; автоматически менять auth mode запрещено.
6. Кульминация: вход успешен, персональная ConfigEntry готова принимать direct-message events.

Failure path: mode административно отключён или credentials отклонены → показать unsupported/reauth для того же mode и направить к tenant administrator; не эмулировать browser login и не выполнять downgrade.

### Создать первую automation

1. Читатель сначала видит `privacy-callout` и понимает, что `message_text` скрыт по умолчанию.
2. Проверяет полный `event-schema` v1 и redacted example `time_messenger_event`.
3. Переходит к первому `automation-recipe`: обычному notification, которое не зависит от специальных устройств integration.
4. Копирует YAML, заменяет целевые notify service или entity на существующие в своей Home Assistant и сохраняет automation.
5. Отправляет новое чужое обычное сообщение в 1:1 `D` на связанную Time identity.
6. Кульминация: Home Assistant показывает notification; важное сообщение коллеги не пропущено.
7. При необходимости читатель повторяет шаблон для light blink или TTS.

Failure path: event приходит с `message_text: null` → automation использует безопасные metadata либо читатель осознанно включает передачу текста; если событие не приходит, читатель переходит к troubleshooting и проверяет ограничения канала, tenant и состояние reconnect.

### Восстановить работу или удалить integration

1. Читатель находит `troubleshooting-item` по наблюдаемому симптому.
2. При auth failure запускает reauth того же mode; при transient disconnect ждёт supervised reconnect.
3. Если проблема сохраняется, собирает только redacted diagnostics и открывает `support-link` issue tracker.
4. Если integration больше не нужна, читатель выполняет removal steps. Локальные credentials и dedupe state очищаются; для Session integration пытается выполнить logout в режиме best effort.
5. Кульминация: работа восстановлена без раскрытия secrets либо integration полностью удалена локально понятным и проверяемым способом.

Failure path: наличие remote revoke endpoint для OAuth/PAT не подтверждено → локальное удаление всё равно завершается; README не обещает remote revoke.
