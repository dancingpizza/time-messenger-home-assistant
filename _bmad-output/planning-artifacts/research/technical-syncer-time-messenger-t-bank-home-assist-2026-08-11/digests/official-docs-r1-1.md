# Раунд 1 — официальные материалы и зрелость Syncer / Time Messenger

Дата среза: 2026-08-11  
Направление: официальные страницы, документация, доступность интеграций, признаки зрелости  
Метод: только прочитанные в этом раунде первичные/официальные источники и страницы магазинов приложений; проектный контекст не использован как доказательство.

## Короткий вывод

Официально документированный продукт Т‑Банка называется **Time** / **Time Messenger**; правообладателем в юридической документации названо ООО «Тинькофф Центр Разработки» (ТЦР). У него есть публичный коммерческий сайт, пользовательская и администраторская документация, API v4/v5, cookbook интеграций, OAuth2, webhooks, боты, slash-команды, SaaS и on-premise поставка.

**Syncer** — действующее отдельное приложение, которое в App Store и RuStore публикует **ARCTERA AM, LLC / Arctera AM**. Официального первичного источника, который прямо называет Syncer новым именем Time, форком, white-label-сборкой или переданным продуктом, в этом раунде не найдено. Сходство позиционирования и функций заметно, но юридическую/техническую преемственность следует считать гипотезой до подтверждения.

Для внешних интеграций Time выглядит доступным на уровне API и расширений, но не как полностью открытая developer platform: для рабочих токенов, OAuth-приложения, бота и интеграций нужен развернутый tenant и административные права; публичного sandbox, self-service developer console и официальных SDK/репозитория продукта не обнаружено.

## Claims

### 1. Официальное имя и владелец Time

- claim: В официальной политике продукт называется «Time» и определяется как iOS/Android-приложения плюс web/desktop-компоненты корпоративного мессенджера; обладателем исключительного права указан ООО «Тинькофф Центр Разработки» (ОГРН 5167746308549).
- URL: https://docs.time-messenger.ru/deployment/operation-and-update-policy/
- publisher: ООО «Тинькофф Центр Разработки» / T‑Bank
- pub_date: n.d. (страница имеет copyright 2026)
- accessed: 2026-08-11
- confidence: high
- class: landscape

### 2. Time — внешний коммерческий продукт, а не только внутренний чат банка

- claim: Официальный сайт предлагает внешним организациям бесплатный тест, SaaS и on-premise, гостевые аккаунты, миграцию из Slack/Mattermost/Rocket.Chat и интеграции через API, Webhook и плагины; отдельно заявлено внутреннее внедрение на 50 000 сотрудников Т‑Банка.
- URL: https://time-messenger.ru/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (страница актуальна в 2026)
- accessed: 2026-08-11
- confidence: high для наличия предложения и заявленных возможностей; medium для маркетинговых чисел без независимой проверки
- class: landscape

### 3. Публичная документация Time шире обычной пользовательской справки

- claim: Публичный портал содержит разделы API, развертывания, администрирования, интеграций, условий и лицензий; пользовательское руководство вынесено на основной домен. Это позволяет оценивать архитектуру интеграции до покупки.
- URL: https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B2%D0%B5%D0%B4%D0%B5%D0%BD%D0%B8%D0%B5/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (портал имеет copyright 2026)
- accessed: 2026-08-11
- confidence: high
- class: ecosystem

### 4. API предназначен и для сторонних приложений

- claim: Официальное введение прямо говорит, что API веб-сервисов Time используется клиентами Time и сторонними приложениями; портал одновременно публикует ветки API v4 и v5.
- URL: https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B2%D0%B5%D0%B4%D0%B5%D0%BD%D0%B8%D0%B5/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (портал имеет copyright 2026)
- accessed: 2026-08-11
- confidence: high
- class: version-compatibility

### 5. Практические механизмы внешней интеграции документированы

- claim: Cookbook описывает входящие webhooks, API-ботов с Bearer-токеном, персональные токены и slash-команды; исходящие webhooks отключены по требованиям информационной безопасности. Персональный токен требует роли `system_user_access_token`, которую включает и назначает администратор.
- URL: https://docs.time-messenger.ru/api/cookbook/intro-integration/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (страница доступна на портале 2026)
- accessed: 2026-08-11
- confidence: high
- class: ecosystem

### 6. OAuth2 поддерживается как встроенная функция tenant-а

- claim: Time может быть OAuth2 service provider для внешних приложений; администратор включает провайдер, регистрирует приложение и получает Client ID/Secret. Документированы Authorization Code и Implicit Grant, refresh token и пример клиента на Go.
- URL: https://docs.time-messenger.ru/integrations/oauth2_service_provider/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (страница доступна на портале 2026)
- accessed: 2026-08-11
- confidence: high
- class: ecosystem

### 7. У продукта есть формализованная релизная и совместимостная политика

- claim: ТЦР обещает релизы не реже раза в квартал; заказчику рекомендовано обновляться в течение двух недель, а инсталляция не должна отставать более чем на один квартальный релиз. Переход на соседний релиз заявлен без остановки серверов, пропуск версий требует остановки.
- URL: https://docs.time-messenger.ru/deployment/operation-and-update-policy/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (страница имеет copyright 2026)
- accessed: 2026-08-11
- confidence: high как политика вендора; фактическое соблюдение не проверено
- class: version-compatibility

### 8. Time распространяется на большом наборе клиентских платформ, но версии сборок публично не показаны

- claim: Официальная страница загрузки предлагает Android, macOS (Intel/arm64), Windows, Linux (x64/arm64) и Aurora (aarch64/armv7); для iOS временно указана только PWA. Номера версий и даты сборок на странице отсутствуют, что ограничивает независимую проверку совместимости.
- URL: https://downloads.time-messenger.ru/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high
- class: version-compatibility

### 9. Syncer сейчас имеет другого публичного издателя

- claim: App Store называет приложение «Syncer», разработчика Arctera и провайдера ARCTERA AM, LLC; указаны iOS 15+, macOS 12+ на Apple Silicon и copyright ARCTERA AM, LLC. Страница не упоминает Т‑Банк, ТЦР или Time.
- URL: https://apps.apple.com/gb/app/syncer/id6751410378
- publisher: Apple App Store; сведения о продукте предоставлены ARCTERA AM, LLC
- pub_date: n.d. (история начинается с версии 1.0 от 2025-09-04)
- accessed: 2026-08-11
- confidence: high для издателя/совместимости; high для отсутствия упоминания на прочитанной странице
- class: landscape

### 10. Syncer активно выпускается на Android

- claim: RuStore показывает Syncer от Arctera AM, пакет `com.messenger.corp.syncer.app`, 40 тыс.+ скачиваний, Android 9+, версию 2.7 от 2026-07-02 и поддержку по адресу `info@arctera.am`. Это свежий сигнал эксплуатации и релизной активности, но не доказательство связи с Time.
- URL: https://www.rustore.ru/catalog/app/com.messenger.corp.syncer.app
- publisher: RuStore / VK; карточка разработчика Arctera AM
- pub_date: 2026-07-02 (версия 2.7)
- accessed: 2026-08-11
- confidence: high
- class: version-compatibility

### 11. Связь Syncer ↔ Time официально не установлена

- claim: По прочитанным официальным материалам существуют две текущие публичные идентичности: Time с правообладателем ТЦР/T‑Bank и Syncer с издателем ARCTERA AM, LLC. Ни один найденный первичный источник не объясняет их отношение. Поэтому утверждать «Syncer — это переименованный Time» пока нельзя; допустима только гипотеза о технологической или организационной преемственности.
- URL: https://docs.time-messenger.ru/deployment/operation-and-update-policy/ ; https://apps.apple.com/gb/app/syncer/id6751410378
- publisher: ООО «ТЦР» / T‑Bank; Apple / ARCTERA AM, LLC
- pub_date: n.d.
- accessed: 2026-08-11
- confidence: high для расхождения издателей; low для любой конкретной модели связи
- class: landscape

### 12. Документация имеет признаки зрелости, но также заметный drift

- claim: Наличие v4/v5, cookbook, OAuth2, deployment/admin/licensing-разделов и квартальной релизной политики — признаки зрелого enterprise-продукта. Одновременно одна страница противоречит сама себе: в тарифном блоке SaaS указан от 50 лицензий и on-premise от 500, а FAQ ниже говорит соответственно от 100 и минимум 1 000; это признак несинхронного обновления публичной документации.
- URL: https://time-messenger.ru/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (страница актуальна в 2026)
- accessed: 2026-08-11
- confidence: high
- class: ecosystem

## Оценка зрелости и внешней доступности

- **Зрелость эксплуатации: medium-high.** Есть заявленное массовое внутреннее внедрение, SaaS/on-premise, SLA, миграции, формальная политика обновлений и широкий набор клиентов. Числа нагрузки и SLA в этом раунде не проверялись независимо.
- **Зрелость developer experience: medium.** API v4/v5 и несколько механизмов интеграции хорошо видимы публично, есть cookbook и код-пример. Не найдены SDK, OpenAPI/Swagger-артефакт, публичный sandbox, changelog API или публичный issue tracker.
- **Доступность внешнему интегратору: medium.** Документацию можно читать без авторизации, но практически нужны tenant, административное включение функций и токены. Это enterprise-интеграция после приобретения/развертывания, а не открытая consumer API.
- **Определенность вокруг Syncer: low.** Приложение живое и обновляется, но публичная документация и юридическое объяснение его связи с Time отсутствуют.

## Leads

1. Запросить у продаж/поддержки Time и у `info@arctera.am` письменное подтверждение: Syncer — новое имя, отдельный продукт, white-label или зарубежная сборка; кто владеет серверной частью и API.
2. Проверить карточки Роспатента/реестр российского ПО и условия лицензии на предмет смены правообладателя после 2025-09-04.
3. Получить доступ к тестовому tenant и проверить фактическую совместимость API v4/v5, персональные токены, webhooks и OAuth2; особое внимание — доступности событий, которые потребуются Home Assistant.
4. Найти/запросить machine-readable API schema и changelog: публичный портал показывает эндпоинты, но без обнаруженного публичного SDK и явной матрицы версий клиентов/сервера.
5. Сравнить сетевые endpoints и API-пути приложений Time и Syncer в разрешенной тестовой среде; это даст техническое, но не юридическое доказательство родства.

## Not found

- Официальное объявление Т‑Банка/Т‑Технологий/ТЦР или Arctera AM о переименовании Time в Syncer, продаже, лицензировании или партнерстве.
- Официальный продуктовый сайт, help/API portal или developer portal именно под брендом Syncer.
- Публичные репозитории исходного кода Time/Syncer, официальные SDK или публичный issue tracker продукта.
- Публичный sandbox или self-service выдача API-ключа без tenant/администратора.
- Явный API changelog, даты релизов API v4/v5 и точная матрица совместимости server/client.
- Публично отображаемые версии desktop/Linux/Aurora-сборок Time на официальной download-странице.

## Прочитанные источники (8)

1. Time: официальный продуктовый сайт — https://time-messenger.ru/
2. Time: политика работы и обновлений — https://docs.time-messenger.ru/deployment/operation-and-update-policy/
3. Time: API v4, введение — https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B2%D0%B5%D0%B4%D0%B5%D0%BD%D0%B8%D0%B5/
4. Time: cookbook интеграций — https://docs.time-messenger.ru/api/cookbook/intro-integration/
5. Time: OAuth2 Service Provider — https://docs.time-messenger.ru/integrations/oauth2_service_provider/
6. Time: официальная страница загрузок — https://downloads.time-messenger.ru/
7. Syncer: App Store — https://apps.apple.com/gb/app/syncer/id6751410378
8. Syncer: RuStore — https://www.rustore.ru/catalog/app/com.messenger.corp.syncer.app
