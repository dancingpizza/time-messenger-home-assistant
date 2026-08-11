# Раунд 2 — прямая связь Syncer ↔ Time

Дата среза: 2026-08-11  
Тип: lead-following / technical research  
Ограничения: только публично доступные первичные или авторитетные источники; без сетевого реверс-инжиниринга, обхода доступа и использования проектного контекста как доказательства.

## Conclusion

**Прямая юридическая или официально объявленная связь Syncer ↔ Time не подтверждена.** После целевого поиска не найдено заявления Т‑Банка, Т‑Технологий, ООО «ТЦР» или ARCTERA AM, LLC о переименовании, передаче прав, лицензировании, white-label-поставке либо создании Syncer на базе Time.

Установлены три более узких факта:

1. ООО «ТЦР» в 2026 году продолжает публично заявлять **исключительное право на «Корпоративный мессенджер Time»**, включенный в Единый реестр российского ПО под № 28364 от 2025-06-06.
2. Time и Syncer существуют как **разные Android-листинги**: `ru.corporate.messenger.app` против `com.messenger.corp.syncer.app`, с разными публичными издателями — Corporate Messenger Time/Россия и Arctera AM/Армения. Поэтому Syncer не является простым переименованием прежней карточки Time в магазине.
3. Описания и набор заявленных функций двух приложений очень близки, местами структурно почти совпадают. Это дает **medium-confidence гипотезу общей продуктовой линии, лицензированной/white-label или производной сборки**, но не позволяет выбрать конкретную модель связи.

Итоговая эпистемическая позиция: **Time ↔ T‑Банк/ТЦР — доказано; Syncer ↔ ARCTERA AM, LLC — доказано; Time ↔ Syncer — вероятная техническая преемственность, но официально не доказана.**

## Claims

### 1. ТЦР продолжает заявлять исключительное право на Time

- claim: Официальная страница ООО «ТЦР» на домене Т‑Банка перечисляет «Корпоративный мессенджер Time» среди ПО, на которое организация имеет исключительное право, и указывает реестровую запись № 28364 от 2025-06-06. В этом перечне нет продукта с названием Syncer.
- URL: https://www.tbank.ru/software/tcr/company-info/
- publisher: ООО «ТЦР» / T‑Bank
- pub_date: n.d. (страница прочитана в актуальном состоянии 2026)
- accessed: 2026-08-11
- confidence: high
- class: landscape

### 2. Запись реестра связывает Time с ТЦР, а не с Arctera

- claim: Каталог совместимости АРПП «Отечественный софт» указывает для «Корпоративного мессенджера Time» вендора ТЦР, номер Единого реестра российского ПО 28364 и дату решения 2025-06-06; ссылка ведет на карточку Минцифры `reestr/3392710/`.
- URL: https://catalog.arppsoft.ru/product/6425017
- publisher: АРПП «Отечественный софт» при поддержке Центра компетенций по импортозамещению в сфере ИКТ
- pub_date: 2025-06-06 (дата решения о включении)
- accessed: 2026-08-11
- confidence: high; прямая карточка Минцифры вернула 403, но сведения независимо совпадают с официальной страницей ТЦР
- class: landscape

### 3. Официальная Android-карточка Time остается отдельной и действующей

- claim: Google Play показывает «Корпоративный мессенджер Time» по package ID `ru.corporate.messenger.app`, издателя Corporate Messenger Time, страну разработчика Russia и последнее обновление 2026-01-20. Карточка продолжает использовать бренд Time после появления Syncer.
- URL: https://play.google.com/store/apps/details?id=ru.corporate.messenger.app&hl=ru
- publisher: Google Play; сведения предоставлены разработчиком Corporate Messenger Time
- pub_date: 2026-01-20 (последнее обновление)
- accessed: 2026-08-11
- confidence: high
- class: version-compatibility

### 4. Syncer — отдельный Android package и отдельный издатель

- claim: RuStore показывает Syncer по package ID `com.messenger.corp.syncer.app`, разработчика Arctera AM и адрес поддержки `info@arctera.am`; версия 2.7 датирована 2026-07-02. Отличающийся package ID означает отдельное Android-приложение/листинг, а не переименование существующего package Time.
- URL: https://www.rustore.ru/catalog/app/com.messenger.corp.syncer.app
- publisher: RuStore / VK; сведения предоставлены Arctera AM
- pub_date: 2026-07-02 (версия 2.7)
- accessed: 2026-08-11
- confidence: high
- class: version-compatibility

### 5. iOS-издателем Syncer также является ARCTERA AM, LLC

- claim: App Store называет провайдером и правообладателем карточки Syncer компанию ARCTERA AM, LLC; история iOS-листинга начинается с версии 1.0 от 2025-09-04. Карточка не упоминает Time, Т‑Банк, Т‑Технологии или ТЦР.
- URL: https://apps.apple.com/gb/app/syncer/id6751410378
- publisher: Apple App Store; сведения предоставлены ARCTERA AM, LLC
- pub_date: 2025-09-04 (первая указанная версия)
- accessed: 2026-08-11
- confidence: high
- class: landscape

### 6. Разные package ID опровергают только простой сценарий rename-in-place

- claim: Пара `ru.corporate.messenger.app` / `com.messenger.corp.syncer.app` доказывает, что мобильные поставки оформлены отдельно. Она не позволяет определить, являются ли кодовые базы независимыми, форком, лицензированной сборкой или white-label-вариантом.
- URL: https://play.google.com/store/apps/details?id=ru.corporate.messenger.app&hl=ru ; https://www.rustore.ru/catalog/app/com.messenger.corp.syncer.app
- publisher: Google Play / Corporate Messenger Time; RuStore / Arctera AM
- pub_date: 2026-01-20; 2026-07-02
- accessed: 2026-08-11
- confidence: high для отдельных package; low для модели происхождения
- class: ecosystem

### 7. Текстовое и функциональное сходство — lead, не подтверждение прав

- claim: Обе карточки описывают SSO, корпоративные и личные чаты, отложенные/регулярные сообщения, реакции и упоминания, интеграции, автоматизацию, SLA, миграцию и масштабирование на десятки тысяч пользователей в почти одинаковой последовательности. Это сильный признак общей продуктовой основы или переиспользования продуктового текста, но магазины не подтверждают источник кода и правоотношения.
- URL: https://play.google.com/store/apps/details?id=ru.corporate.messenger.app&hl=ru ; https://www.rustore.ru/catalog/app/com.messenger.corp.syncer.app
- publisher: Google Play / Corporate Messenger Time; RuStore / Arctera AM
- pub_date: 2026-01-20; 2026-07-02
- accessed: 2026-08-11
- confidence: medium
- class: ecosystem

## Searched_and_not_found

- На официальных доменах `tbank.ru` и `t-technologies.ru` не найден пресс-релиз или продуктовая страница, связывающая название Syncer с Time, Т‑Банком, Т‑Технологиями или ТЦР.
- На официальных страницах ТЦР не найден Syncer среди ПО, исключительные права на которое заявляет ТЦР; актуальный перечень продолжает называть Time.
- Не найден официальный сайт или юридическая страница ARCTERA AM, LLC, где Syncer был бы описан как продукт, приобретенный/лицензированный у Т‑Банка или ТЦР.
- Не найден документ о передаче исключительного права, лицензионный договор, партнерское объявление, white-label agreement или уведомление о смене правообладателя Time.
- В поиске по названию Syncer не найдена отдельная запись российского реестра ПО; найденная запись № 28364 относится к Time и ТЦР.
- Не найдено объяснение роли `t-software` применительно к Syncer/Time. Результаты по одноименным зарубежным компаниям не использованы как доказательство.
- Прямая карточка Минцифры `https://reestr.digital.gov.ru/reestr/3392710/` обнаружена через каталог АРПП, но сервер вернул HTTP 403; обход ограничения не предпринимался.
- Официальный Android-листинг Syncer в Google Play по package ID в этом раунде не открылся; для package ID и издателя использована доступная официальная карточка RuStore.

## Прочитанные источники

1. ООО «ТЦР»: информация о компании и исключительных правах — https://www.tbank.ru/software/tcr/company-info/
2. Каталог АРПП: запись Time № 28364 — https://catalog.arppsoft.ru/product/6425017
3. Google Play: Time, `ru.corporate.messenger.app` — https://play.google.com/store/apps/details?id=ru.corporate.messenger.app&hl=ru
4. RuStore: Syncer, `com.messenger.corp.syncer.app` — https://www.rustore.ru/catalog/app/com.messenger.corp.syncer.app
5. Apple App Store: Syncer — https://apps.apple.com/gb/app/syncer/id6751410378
