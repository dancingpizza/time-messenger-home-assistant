---
title: "Визуальный дизайн документации Time Messenger integration"
name: "Time Messenger for Home Assistant Docs"
description: "Лёгкая, технически точная документация неофициальной integration для GitHub README и HACS."
status: final
created: 2026-08-11
updated: 2026-08-11
sources:
  - ../../../specs/spec-hacs-documentation-branding/SPEC.md
  - ../../../specs/spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md
  - ../../../specs/spec-syncer-time-messenger-t-bank-home-assist/authentication-methods.md
  - ../../architecture/architecture-syncer-ha-2026-08-11/ARCHITECTURE-SPINE.md
  - ../../research/technical-syncer-time-messenger-t-bank-home-assist-2026-08-11/research.md
typography:
  page-title:
    note: "Нативный Markdown H1 в GitHub и HACS"
  section-title:
    note: "Нативный Markdown H2; H3 только для подразделов внутри секции"
  body:
    note: "Нативный пропорциональный шрифт GitHub и HACS"
  code:
    note: "Нативный моноширинный шрифт fenced code block"
spacing:
  compact-gap: 8px
  content-gap: 16px
  section-gap: 24px
components:
  readme-intro:
    title: "{typography.page-title.note}"
    body: "{typography.body.note}"
    spacing-after: "{spacing.content-gap}"
  use-case-teaser:
    title: "{typography.section-title.note}"
    body: "{typography.body.note}"
    spacing-between-items: "{spacing.compact-gap}"
  compatibility-callout:
    body: "{typography.body.note}"
    spacing-block: "{spacing.content-gap}"
  installation-sequence:
    title: "{typography.section-title.note}"
    body: "{typography.body.note}"
    spacing-between-steps: "{spacing.compact-gap}"
  auth-choice:
    title: "{typography.section-title.note}"
    body: "{typography.body.note}"
    spacing-between-options: "{spacing.content-gap}"
  privacy-callout:
    title: "{typography.section-title.note}"
    body: "{typography.body.note}"
    spacing-block: "{spacing.content-gap}"
  event-schema:
    title: "{typography.section-title.note}"
    code: "{typography.code.note}"
    spacing-block: "{spacing.content-gap}"
  automation-recipe:
    title: "{typography.section-title.note}"
    code: "{typography.code.note}"
    spacing-block: "{spacing.content-gap}"
  troubleshooting-item:
    title: "{typography.section-title.note}"
    body: "{typography.body.note}"
    spacing-between-items: "{spacing.content-gap}"
  support-link:
    body: "{typography.body.note}"
    spacing-block: "{spacing.content-gap}"
---

## Brand & Style

Документация выглядит как короткое, доброжелательное техническое руководство для человека, который уже знаком с Home Assistant. Первый экран показывает практический результат: сообщение коллеги запускает automation. Он не продаёт идею и не объясняет основы Home Assistant.

Метафора хорошей детской книги означает только ясность, короткий путь и лёгкость чтения. Сказочный сюжет, детская стилизация, вымышленный герой и инфантилизирующий тон запрещены. Визуальная идентичность юридически нейтральна: не использовать логотипы, товарные знаки и фирменные мотивы Time или Т-Банка.

README использует только нативный Markdown GitHub/HACS без custom CSS и custom frontend. Поэтому этот контракт управляет иерархией, плотностью и композицией контента, а палитру, шрифты, ссылки, фокус и code blocks рендерит платформа.

## Typography

- `{typography.page-title}` используется один раз для названия проекта.
- `{typography.section-title}` делит длинную страницу на самостоятельные задачи. H3 допустим только внутри H2; заголовки глубже H3 запрещены.
- `{typography.body}` задаёт короткие абзацы простым языком. Один абзац несёт одну мысль; длинные стены инструкций запрещены.
- `{typography.code}` применяется только к командам, event payload и готовым YAML recipes. Код не заменяет объяснение результата и ограничения.
- Жирное начертание выделяет ключевой выбор или предупреждение. Inline code отмечает точное имя поля, event, пути или версии. Целые абзацы не выделяются.

## Layout & Spacing

README представляет собой одноколоночную вертикальную страницу. Ритм строится вокруг коротких автономных секций: `{spacing.section-gap}` между крупными задачами, `{spacing.content-gap}` между объяснением и связанным блоком, `{spacing.compact-gap}` между тесно связанными пунктами. Значения задают целевой ритм; фактические отступы наследуются от GitHub/HACS Markdown renderer.

Первый экран содержит `readme-intro`, три коротких `use-case-teaser` и компактный `compatibility-callout`; затем сразу начинается `installation-sequence`. Полные recipes, event schema, privacy и troubleshooting располагаются ниже. Широкие таблицы не использовать: различия auth mode лучше давать вертикальными блоками или компактным списком, чтобы структура не ломалась на mobile.

Визуальная лёгкость достигается короткими секциями, воздухом и понятными callouts, а не декоративной перегрузкой. Страница одинаково читаема в HACS, GitHub desktop и mobile: смысл не зависит от широкой таблицы или только от цвета.

## Components

| Component | Визуальная спецификация |
|---|---|
| `readme-intro` | Один `{typography.page-title}`, короткий body block и одна отдельная строка English summary. Пометка о неофициальном статусе находится в том же viewport. Hero-изображения нет. |
| `use-case-teaser` | Компактный вертикальный список. Каждый teaser занимает не больше двух строк body text. Иконки и декоративные карточки не нужны. |
| `compatibility-callout` | Короткий самостоятельный body block в верхней части страницы. Метка и текст различимы без цветовой заливки. |
| `installation-sequence` | Нумерованный список с `{spacing.compact-gap}` между шагами. Основной путь идёт первым; recovery subsection визуально отделён подзаголовком. |
| `auth-choice` | Три вертикальных блока с одинаковой анатомией: название, короткая метка, body text. Порядок и метки создают иерархию; равнозначные карточки и цветовая кодировка запрещены. |
| `privacy-callout` | Отдельный короткий блок перед code section. Ключевое значение оформляется inline code, а не цветным badge или сноской. |
| `event-schema` | H2 или H3, поясняющий body text и fenced code block `{typography.code}`. Redacted example находится в отдельном code block с подписью. |
| `automation-recipe` | H3, одна строка body text и fenced YAML block `{typography.code}`. Все recipe blocks имеют одинаковую композицию. |
| `troubleshooting-item` | H3 по наблюдаемому симптому, затем короткие абзацы причины и действия. Между items используется `{spacing.content-gap}`. |
| `support-link` | Обычная текстовая ссылка в заключительной секции. Подпись называет назначение; декоративная кнопка не используется. |

Нативные Markdown-элементы наследуют визуальные состояния платформы. Контраст обычного текста, ссылок, code blocks и индикатора фокуса должен соответствовать WCAG 2.2 AA; новые цветовые переопределения не вводятся.

## Do's and Don'ts

| Делать | Не делать |
|---|---|
| Начинать с конкретной пользы и быстро вести к установке | Начинать с архитектуры, auth или длинного списка ограничений |
| Писать короткими секциями и показывать один следующий шаг | Создавать «талмуд», глубокое оглавление или длинные сквозные инструкции |
| Отделять тизер результата от полного YAML recipe | Показывать YAML на первом экране |
| Называть recipes пользовательскими automation | Обещать встроенную поддержку Алисы, ламп или notification actions |
| Сохранять нативную читаемость GitHub/HACS | Полагаться на custom CSS, широкие таблицы, цвет без текстовой метки или motion |
| Использовать нейтральные оригинальные assets с alt text | Использовать логотипы и товарные знаки Time или Т-Банка |
| Явно показывать ограничения без драматизации | Обещать gap-free delivery, любой tenant, `G/P/O` или доступность всех auth modes |
