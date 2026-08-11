---
id: SPEC-hacs-documentation-branding
companions:
  - ../spec-syncer-time-messenger-t-bank-home-assist/SPEC.md
  - ../spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md
  - ../spec-syncer-time-messenger-t-bank-home-assist/authentication-methods.md
  - ../../planning-artifacts/ux-designs/ux-syncer-ha-2026-08-11/DESIGN.md
  - ../../planning-artifacts/ux-designs/ux-syncer-ha-2026-08-11/EXPERIENCE.md
sources: []
---

> **Канонический контракт.** Эта SPEC и файлы из `companions:` задают полный preservation-validated контракт для HACS landing page, пользовательской документации и нейтрального brand asset.

# Документация и branding для HACS

## Why

Технически уверенный пользователь Home Assistant не должен читать исходный код или тяжёлый мануал, чтобы установить integration, выбрать доступный способ входа и не пропускать сообщения коллег. HACS нужен лёгкий, дружелюбный и юридически нейтральный presentation layer для repository.

## Capabilities

- **CAP-8**
  - **intent:** Пользователь до установки может оценить совместимость, ограничения и безопасно настроить integration и свои автоматизации.
  - **success:** HACS отображает humanized README по обязательным `DESIGN.md` и `EXPERIENCE.md` с установкой, auth hierarchy, privacy, event schema v1, recipes, troubleshooting, removal и support; repository содержит валидную нейтральную raster icon.

## Constraints

- Финальные `DESIGN.md` и `EXPERIENCE.md` являются adopted companions и обязательным UX-контрактом; при конфликте с mockups или imports выигрывают spines.
- README использует native GitHub/HACS Markdown и UX-порядок: короткая польза и use-case тизеры, compatibility, установка, auth hierarchy, privacy/schema, recipes, эксплуатация и support.
- Установка описывает custom repository `dancingpizza/time-messenger-home-assistant`, HACS My link, restart, config flow и manual recovery copy только `custom_components/time_messenger`.
- Auth hierarchy фиксирован: OAuth рекомендуется при организационной настройке, PAT является простым самостоятельным вариантом при разрешении, Session остаётся fallback; automatic auth fallback запрещён.
- Приводится полный redacted `time_messenger_event` schema v1 и минимальные YAML recipes для notification, мигания света и TTS; это пользовательские automation, не встроенные действия integration.
- Privacy-раздел фиксирует `message_text: null` по умолчанию и запрет secrets/raw payload в logs и diagnostics.
- README не обещает gap-free delivery, любой tenant, каналы `G/P/O` или доступность всех auth modes при административных ограничениях.
- Fictional hero, сказочный сюжет, инфантилизация, custom CSS, wide tables, color-only meaning и decorative motion запрещены.
- После factual и structural checks README обязательно проходит skill `humanizer`: draft, still-AI audit, final без потери фактов, code blocks или URLs; публикуется только final, audit evidence остаётся в implementation verification.
- Humanized final не содержит em/en dash и AI-writing patterns, перечисленных в `EXPERIENCE.md` Humanizer Gate.
- Иконка — оригинальный нейтральный bitmap без текста, логотипов и товарных знаков Time или Т-Банка; финальный asset сохраняется в repository.
- CAP-1–CAP-7, CAP-9–CAP-10 и AD-1–AD-13 не меняются; push и GitHub Release не выполняются.

## Non-goals

- Изменение config flow, runtime или event schema.
- Default HACS submission, Home Assistant Brands submission и использование фирменных знаков третьих лиц.
- Встроенные automation actions, dashboards, custom frontend и отдельный README mockup.

## Success signal

Новый пользователь по одному humanized README устанавливает integration, осознанно выбирает auth mode и запускает notification automation по redacted event example. UX Definition of Done и Humanizer Gate пройдены, а проверка изображения подтверждает пригодный raster asset без сторонней символики.
