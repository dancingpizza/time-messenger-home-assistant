# Раунд 1 — API и интероперабельность Time Messenger / «Syncer»

Дата исследования: 2026-08-11  
Направление: официальный API, события, аутентификация и применимость к Home Assistant  
Метод: поиск и чтение официальной документации Time/T‑Банка; проектный контекст не использовался как доказательство.

## Краткий вывод

У Time Messenger есть документированный интеграционный контур, достаточный для двусторонней интеграции с Home Assistant без браузерной автоматизации: REST API v4, OpenAPI-спецификация, входящие и исходящие вебхуки, бот-аккаунты, быстрые/slash-команды и аутентифицированный WebSocket с событиями сообщений, реакций, файлов и состояния каналов. Самый простой путь для уведомлений HA → Time — входящий вебхук; для команд Time → HA — исходящий вебхук или быстрая команда; для устойчивой двусторонней интеграции — бот/персональный токен + REST, а для низкой задержки — WebSocket.

Ключевая оговорка: публичная документация не обнаруживает готовую официальную интеграцию Home Assistant, официальный SDK или подтвержденное соответствие названия «Syncer» текущему продукту Time. Текущая официальная идентичность продукта — Time Messenger; T‑API Т‑Банка является отдельным банковским API и не должна смешиваться с API мессенджера.

## Claims

### C1 — REST API v4 и схема

- **claim:** Time документирует HTTPS REST API с базовым путем `/api/v4`; тела запросов и ответов — `application/json`. Опубликован `openapi.yaml`, который разрешено использовать для генерации клиентских SDK.
- **URL:** https://docs.time-messenger.ru/api/v4/%D1%81%D1%85%D0%B5%D0%BC%D0%B0/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** version-compatibility

### C2 — API v5 присутствует, но v4 остается основным документированным интеграционным контуром

- **claim:** Официальный сайт одновременно публикует документацию API v4 и API v5; справочник v5 помечен как Version 5.0 и использует заголовок `Authorization` в схеме `access_token`. Публичная документация не дает на обзорных страницах явного срока вывода v4 из эксплуатации или полной матрицы паритета v4/v5, поэтому выбор v5 для HA требует проверки нужных эндпоинтов по отдельности.
- **URL:** https://docs.time-messenger.ru/api/v5/time-api-reference/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** medium
- **class:** version-compatibility

### C3 — способы аутентификации API

- **claim:** API v4 поддерживает сессионный токен после `POST /api/v4/users/login`, персональный токен доступа и OAuth 2.0; токены передаются как `Authorization: Bearer …`. Персональный токен не истекает сам и действует до ручного отзыва пользователем или администратором.
- **URL:** https://docs.time-messenger.ru/api/v4/%D0%B0%D1%83%D1%82%D0%B5%D0%BD%D1%82%D0%B8%D1%84%D0%B8%D0%BA%D0%B0%D1%86%D0%B8%D1%8F/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** security

### C4 — интеграционные сущности и управление токенами

- **claim:** В интерфейсе пространства документированы входящие вебхуки, исходящие вебхуки, быстрые команды, OAuth 2.0-приложения и бот-аккаунты. Доступность типов интеграций определяет системный администратор; у одного бота может быть несколько активных токенов; обычный участник видит только созданных им ботов, администратор — всех.
- **URL:** https://time-messenger.ru/documentation/integrations/
- **publisher:** Time Messenger / ООО «ТЦР»
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** security

### C5 — сообщения, чаты, файлы и другие модели доступны через API

- **claim:** Каталог v4 содержит группы эндпоинтов для пользователей, ботов, команд, каналов, постов (сообщений), обсуждений/веток, файлов, реакций, приложений, вебхуков, slash-команд, OAuth, ролей и плагинов. Для постов документированы создание, чтение, изменение, удаление, ветки, поиск, закрепление и сведения о файлах; для файлов — загрузка, получение, удаление, метаданные, превью, временные файлы и поиск.
- **URL:** https://docs.time-messenger.ru/api/v4/users/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** integration

### C6 — real-time поток событий

- **claim:** Помимо REST, Time предоставляет WebSocket на `/api/v4/websocket`. Он аутентифицируется cookie/Authorization или сообщением `authentication_challenge` с токеном. Документированы события `posted`, `post_edited`, `post_deleted`, `reaction_added`, `reaction_removed`, `typing`, `channel_*`, `thread_*`, `file_deleted`, `status_change` и другие; envelope содержит `event`, `data`, `broadcast`, `seq`.
- **URL:** https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** integration

### C7 — лимиты API настраиваемы в On-Premise

- **claim:** В On-Premise ограничение API настраивается администратором и по умолчанию выключено; при включении значение по умолчанию — 10 запросов/с, максимальный burst — 100. Лимит можно варьировать по IP, пользовательскому токену или HTTP-заголовку. Ответы API сообщают состояние через `X-Ratelimit-Limit`, `X-Ratelimit-Remaining`, `X-Ratelimit-Reset`, а превышение возвращает HTTP 429.
- **URL:** https://docs.time-messenger.ru/administration/settings/environment/rate_limiting/
- **publisher:** Time Messenger / T‑Bank
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** security

### C8 — SaaS и On-Premise

- **claim:** Time предлагается как SaaS и On-Premise; публичная продуктовая страница прямо заявляет интеграции через API, Webhook и плагины. Для HA это означает, что базовый URL API зависит от конкретного инстанса, а сетевой доступ к on-prem экземпляру может быть только внутренним.
- **URL:** https://time-messenger.ru/
- **publisher:** Time Messenger / ООО «ТЦР»
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high для вариантов поставки; medium для сетевого вывода
- **class:** integration

### C9 — рекомендуемый паттерн для Home Assistant

- **claim:** Документированные возможности поддерживают три практических паттерна: (1) HA → Time через входящий webhook для уведомлений; (2) Time → HA через исходящий webhook или быструю команду для запуска автоматизации; (3) полноценный custom integration/bridge через bot или personal access token + REST, с WebSocket для событий без polling. Это архитектурный вывод из официальных интерфейсов, а не готовая интеграция производителя.
- **URL:** https://time-messenger.ru/documentation/integrations/
- **publisher:** Time Messenger / ООО «ТЦР»
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high для технической реализуемости; medium для эксплуатационной пригодности без прототипа
- **class:** integration

### C10 — Time API не равен банковскому T‑API

- **claim:** Официальный T‑Bank Dev Portal описывает T‑API как интерфейс банковских бизнес-процессов: платежи, счета, выписки, компании и пользователи, зарплата, самозанятые, СБП и кредитные продукты. Это отдельный API и не источник методов мессенджера Time.
- **URL:** https://developer.tbank.ru/docs/intro/integration-steps
- **publisher:** T‑Bank Dev Portal
- **pub_date:** n.d.
- **accessed:** 2026-08-11
- **confidence:** high
- **class:** integration

## Ограничения и безопасность для реализации

- Секреты входящих вебхуков, bot tokens и personal access tokens следует хранить в `secrets.yaml`/защищенном хранилище HA и не включать в логи; особенно важен ручной отзыв долгоживущих персональных токенов.
- Предпочтителен отдельный bot-аккаунт с минимальными ролями и членством только в нужных каналах. Документация показывает ролевые проверки на уровне эндпоинтов, но общего публичного каталога OAuth scopes в просмотренных материалах не найдено.
- Для real-time клиента нужны reconnect/backoff, обработка дубликатов и восстановление состояния через REST после разрыва: WebSocket описывает формат событий, но публично не обнаружены гарантии доставки, replay cursor или resume semantics.
- В On-Premise нужно согласовать исходящий сетевой маршрут к HA или разместить bridge рядом с Time; для SaaS — безопасно экспонировать callback HA через TLS/reverse proxy либо использовать промежуточный сервис.

## Leads для следующего раунда

1. Скачать и машинно разобрать текущий `openapi.yaml`: составить точную матрицу методов, permission requirements и моделей Post/Channel/File/Bot/OAuth; проверить расхождения v4/v5.
2. Открыть конкретные страницы `Use incoming webhook`, `Create outgoing webhook`, slash commands и OAuth authorization flow: зафиксировать payload, подпись/токен в callback, таймаут ответа, retries и допустимые URL.
3. Проверить, публикует ли Time официальный Docker/Helm-артефакт, клиентскую библиотеку или пример бота вне индексируемой документации.
4. Провести минимальный прототип: HA REST command → incoming webhook; Time outgoing webhook → HA webhook; затем WebSocket `posted` → HA event.
5. Уточнить у поддержки Time политику rate limits и доступность интеграций именно для SaaS-тарифа заказчика.

## Contradictions

- На одной и той же продуктовой странице в карточке тарифа указано On-Premise «от 500 лицензий», а в FAQ — минимально 1 000 лицензий. Это коммерческое противоречие не влияет на API, но требует прямого уточнения у поставщика. Источник: https://time-messenger.ru/ (Time Messenger / ООО «ТЦР», n.d., accessed 2026-08-11, confidence high, class integration).
- Документация одновременно показывает v4 и v5, но не была найдена единая публичная migration/deprecation matrix. Поэтому нельзя считать v5 полной заменой v4 только по номеру версии.

## Not found

- Не найден официальный источник, подтверждающий, что «Syncer» — прежнее или альтернативное название именно текущего Time Messenger. В официальных материалах продукт называется Time/Time Messenger; одноименные Syncer-сервисы из поиска исключены.
- Не найдена готовая официальная интеграция Time для Home Assistant или запись в каталоге интеграций HA.
- Не найден официальный вручную поддерживаемый SDK; подтверждена только OpenAPI-спецификация, пригодная для генерации SDK.
- Не найден официальный публичный репозиторий исходного кода Time Messenger.
- Не найдены в просмотренных источниках: полный перечень OAuth scopes, документированные гарантии/retry-политика исходящих webhook, подпись callback-запросов, WebSocket replay/resume, SLA доставки событий и отдельные SaaS rate limits.
- Не найдено указание на XMPP/Matrix/federation; подтверждены HTTP REST, webhooks и WebSocket.

## Прочитанные источники, использованные как доказательства (8)

1. Time Messenger User Guide — Integrations: https://time-messenger.ru/documentation/integrations/
2. Time API v4 — Schema: https://docs.time-messenger.ru/api/v4/%D1%81%D1%85%D0%B5%D0%BC%D0%B0/
3. Time API v4 — Authentication: https://docs.time-messenger.ru/api/v4/%D0%B0%D1%83%D1%82%D0%B5%D0%BD%D1%82%D0%B8%D1%84%D0%B8%D0%BA%D0%B0%D1%86%D0%B8%D1%8F/
4. Time API v4 — WebSocket: https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82/
5. Time API v4 — endpoint catalog: https://docs.time-messenger.ru/api/v4/users/
6. Time administration — rate limiting: https://docs.time-messenger.ru/administration/settings/environment/rate_limiting/
7. Time Messenger product page: https://time-messenger.ru/
8. T‑Bank Dev Portal — T‑API integration steps: https://developer.tbank.ru/docs/intro/integration-steps

