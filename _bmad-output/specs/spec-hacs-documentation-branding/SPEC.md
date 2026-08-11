---
id: SPEC-hacs-documentation-branding
companions:
  - ../spec-syncer-time-messenger-t-bank-home-assist/SPEC.md
  - ../spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md
  - ../spec-syncer-time-messenger-t-bank-home-assist/authentication-methods.md
sources: []
---

> **Канонический контракт.** Эта SPEC и файлы из `companions:` задают полный контракт для HACS landing page, пользовательской документации и нейтрального brand asset.

# Документация и branding для HACS

## Why

Пользователь не должен читать исходный код, чтобы понять назначение integration, безопасно выбрать способ входа и построить автоматизацию. HACS также нужен узнаваемый, юридически нейтральный presentation layer для repository.

## Capabilities

- **CAP-8**
  - **intent:** Пользователь до установки может оценить совместимость, ограничения и безопасно настроить integration и свои автоматизации.
  - **success:** HACS отображает README с установкой, OAuth/PAT/Session, privacy, event schema v1, recipes, troubleshooting, removal и support links; repository содержит валидную нейтральную raster icon.

## Constraints

- README следует порядку из `distribution-release.md`, начинается русским описанием и коротким English summary и явно называет проект неофициальной Home Assistant integration.
- Установка описывает custom repository `dancingpizza/time-messenger-home-assistant`, HACS My link, restart, config flow и manual recovery copy только `custom_components/time_messenger`.
- Приводится полный redacted `time_messenger_event` schema v1 и минимальные YAML recipes для notification, мигания света и TTS; это пользовательские automation, не встроенные действия integration.
- Privacy-раздел фиксирует `message_text: null` по умолчанию и запрет secrets/raw payload в logs и diagnostics.
- README не обещает gap-free delivery, любой tenant, каналы `G/P/O` или доступность всех auth modes при административных ограничениях.
- Иконка — оригинальный нейтральный bitmap без текста, логотипов и товарных знаков Time или Т-Банка; финальный asset сохраняется в repository.
- CAP-1–CAP-7, CAP-9–CAP-10 и AD-1–AD-13 не меняются; push и GitHub Release не выполняются.

## Non-goals

- Изменение config flow, runtime или event schema.
- Default HACS submission, Home Assistant Brands submission и использование фирменных знаков третьих лиц.
- Встроенные automation actions, dashboards или custom frontend.

## Success signal

Новый пользователь может по одному README установить integration, выбрать auth mode и создать automation по redacted event example, а проверка изображения подтверждает пригодный raster asset без сторонней символики.
