# Time Messenger для Home Assistant

Привет! Эта неофициальная integration превращает новые личные сообщения Time в события Home Assistant. Событие можно использовать в собственной automation, например показать notification или привлечь внимание другим способом.

Unofficial Home Assistant integration for new direct messages from Time Messenger.

Примеры ниже помогут:

- показать обычное notification без специального устройства;
- мигнуть совместимой лампой;
- передать текст сообщения в TTS после явного разрешения.

Версия 0.0.1 принимает только новые чужие обычные сообщения из чатов 1:1 типа `D`. Каналы `G`, `P` и `O`, backfill, gap-free delivery и встроенные automation actions не поддерживаются.

Совместимость: Home Assistant 2026.8.1+, Time API v4 и целевой tenant, который прошел acceptance probe. Python предоставляет сам Home Assistant. Если версия Home Assistant ниже или tenant не проверен, устанавливать integration пока не стоит. Администратор tenant может отключить отдельные способы авторизации.

Acceptance probe запускает администратор или maintainer для каждого разрешенного auth mode. Из корня repository он проверяет identity, WebSocket `hello` и классы входящих событий, не печатая credentials или текст сообщений:

```console
uv run python scripts/probe_time_tenant.py \
  --origin https://time.example.org \
  --auth-mode pat \
  --duration 60
```

Замените `https://time.example.org` на HTTPS origin своего Time tenant.

Для OAuth или PAT probe запросит bearer token без echo. Для Session он запросит login, password и MFA. Встроенная проверка `users/me` и WebSocket `hello` в config flow подтверждает вход, но не заменяет полный acceptance probe с событиями и reconnect.

## Установка

Для remote installation нужен опубликованный GitHub Release. HACS-ссылка начнет устанавливать пакет только после push репозитория и выпуска release.

1. Откройте [добавление custom repository в HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=dancingpizza&repository=time-messenger-home-assistant&category=integration).
2. Если My link недоступна, откройте HACS, затем Custom repositories. Добавьте `dancingpizza/time-messenger-home-assistant` с категорией Integration.
3. Установите Time Messenger и перезапустите Home Assistant.
4. Откройте Settings > Devices & services > Add integration и выберите Time Messenger.

### Ручная установка как recovery

Если HACS недоступен, скопируйте только каталог `custom_components/time_messenger` в каталог `custom_components` вашей конфигурации Home Assistant. Затем перезапустите Home Assistant и повторите четвертый шаг. Не копируйте весь repository в `custom_components`.

## Авторизация

В начале config flow укажите HTTPS origin вашего tenant и выберите один mode. Origin состоит из схемы, host и необязательного port, например `https://time.example.org`. Не добавляйте path, `/api/v4`, query или fragment. Каждый mode проверяет Time identity через `users/me`, затем ожидает WebSocket `hello`. Integration не переключает способ автоматически и не выполняет downgrade. При reauth она остается в том же mode.

### OAuth

Рекомендуемый вариант, если организация зарегистрировала OAuth application для Home Assistant. Получите OAuth Client ID и Client Secret у администратора. В Home Assistant откройте Settings > Devices & services, затем меню с тремя точками > Application credentials. Добавьте credentials для Time Messenger. Если форма показывает authentication domain, укажите в нем тот же normalized tenant origin.

Client credentials хранятся в Home Assistant Application Credentials, а ConfigEntry хранит OAuth token. После истечения access token adapter запрашивает refresh. Если для origin tenant нет зарегистрированной OAuth implementation, integration завершит выбор как unsupported. Другие ошибки registration, scopes, PKCE policy или redirect URI зависят от политики tenant. Ошибка refresh запускает reauth OAuth.

### PAT

Простой self-service вариант, если администратор разрешил personal access tokens. Создайте PAT в Time и вставьте его в config flow. ConfigEntry хранит token как bearer до его отзыва. Ответ `401` запускает reauth PAT. Если PAT запрещены политикой tenant, обратитесь к администратору.

### Session

Fallback для tenant, где API login разрешен. Config flow принимает login, password и при необходимости MFA, но сохраняет только полученный session token. Password и MFA не сохраняются. В SSO-only tenant endpoint входа может быть отключен. Тогда Session помечается как unsupported. Integration не эмулирует browser login. Истекшая или отозванная сессия запускает reauth Session.

## Privacy и event schema

По умолчанию `message_text` равен `null`, а `text_redacted` равен `true`. Это позволяет automation работать с metadata, не раскрывая текст. Передача текста включается через Settings > Devices & services > Time Messenger > Configure и является privacy opt-in. После включения текст попадает во все новые `time_messenger_event` этой ConfigEntry и доступен любому listener или automation с доступом к event bus Home Assistant.

Код этой integration не добавляет secrets и raw payload в свои logs или diagnostics. Event и diagnostics содержат стабильные account, sender, channel, post и tenant identifiers. Эти metadata тоже могут быть чувствительными, поэтому просмотрите diagnostics перед отправкой в issue.

Integration публикует `time_messenger_event` со `schema_version: 1`. Версия schema не связана с версией пакета 0.0.1. Полный redacted example содержит все обязательные и optional поля:

```json
{
  "schema_version": 1,
  "type": "direct_message",
  "config_entry_id": "01JEXAMPLEENTRY",
  "account_user_id": "user-current",
  "post_id": "post-example",
  "channel_id": "channel-example",
  "sender_user_id": "user-colleague",
  "message_text": null,
  "text_redacted": true,
  "created_at": "2026-08-11T12:00:00Z",
  "sender_username": "colleague",
  "root_id": "root-example",
  "file_ids": ["file-example"]
}
```

`created_at` содержит время создания сообщения в UTC в формате ISO 8601. Поля `sender_username`, `root_id` и `file_ids` optional и отсутствуют в событии, когда значения нет. В частности, `file_ids` отсутствует у сообщения без вложений. Остальные поля обязательны. Automation должна уметь использовать `sender_user_id` или другую metadata, если optional поле отсутствует или текст скрыт.

До создания automation можно открыть Developer Tools > Events, начать прослушивание `time_messenger_event` и отправить новое сообщение с другой Time identity. Проверяйте только redacted payload и не публикуйте identifiers из него без необходимости.

## Пользовательские automation recipes

Это обычные automation Home Assistant, а не встроенные actions integration. Добавьте их через UI или `automations.yaml`. При ручном редактировании следуйте правилам вашей конфигурации Home Assistant.

Если настроено несколько ConfigEntry, примеры ниже будут реагировать на события от каждой из них. Чтобы оставить одну account или tenant, добавьте точный `config_entry_id` из ее события в `event_data` рядом с `schema_version` и `type`.

### Notification с metadata fallback

Этот recipe работает без device-specific notify service. Если текст скрыт, notification использует имя или ID отправителя. Если privacy opt-in включен, полное сообщение попадет в persistent notification.

```yaml
alias: Time Messenger, новое личное сообщение
triggers:
  - trigger: event
    event_type: time_messenger_event
    event_data:
      schema_version: 1
      type: direct_message
actions:
  - action: persistent_notification.create
    data:
      title: Time Messenger
      message: >-
        {{ trigger.event.data.message_text
           or ('Новое сообщение от '
               ~ (trigger.event.data.sender_username
                  | default(trigger.event.data.sender_user_id, true))) }}
mode: queued
```

### Мигание света

Замените `light.desk_lamp` на существующую entity. Параметр `flash` поддерживают не все лампы и integration освещения. Если устройство проигнорирует `flash`, лампа может просто включиться и остаться включенной.

```yaml
alias: Time Messenger, мигнуть светом
triggers:
  - trigger: event
    event_type: time_messenger_event
    event_data:
      schema_version: 1
      type: direct_message
actions:
  - action: light.turn_on
    target:
      entity_id: light.desk_lamp
    data:
      flash: short
mode: restart
```

### Озвучивание через TTS

Сначала включите передачу текста через Settings > Devices & services > Time Messenger > Configure. Это разрешает текст для всех новых событий этой ConfigEntry, а не только для TTS. Замените `tts.example` и `media_player.living_room` на доступные TTS и media player entities. Recipe не обещает встроенную поддержку Алисы.

```yaml
alias: Time Messenger, озвучить личное сообщение
triggers:
  - trigger: event
    event_type: time_messenger_event
    event_data:
      schema_version: 1
      type: direct_message
conditions:
  - condition: template
    value_template: >-
      {{ trigger.event.data.message_text
         | default('', true) | trim | length > 0 }}
actions:
  - action: tts.speak
    target:
      entity_id: tts.example
    data:
      media_player_entity_id: media_player.living_room
      message: "{{ trigger.event.data.message_text }}"
mode: queued
```

## Эксплуатация и troubleshooting

### Не удалось войти

Проверьте origin tenant и credentials. Если mode отключен политикой tenant, config flow покажет unsupported. Обратитесь к администратору. Для недействительных credentials запустите reauth того же mode. Автоматической смены на другой mode нет.

### События временно перестали приходить

Listener переподключается после transient network failure. Повторно доставленный `post_id` подавляется сохраненным dedupe state. Integration не обещает backfill или gap-free delivery после полного офлайна. Проверьте состояние ConfigEntry и Repairs. Если entry загружена, но событие не появляется, скачайте redacted diagnostics и только после этого смотрите logs integration, где secrets и raw payload отсутствуют.

### Событие не появилось

Проверьте, что это новое обычное сообщение от другого пользователя в чате 1:1 типа `D`. Собственные сообщения, system и integration posts, а также каналы `G`, `P` и `O` отбрасываются. Если tenant еще не проходил acceptance probe, не считайте его совместимым.

### В событии нет текста

Это штатный privacy default. Automation может использовать metadata fallback. Если текст действительно нужен, включите его передачу в options ConfigEntry и проверьте, куда automation отправляет или озвучивает данные.

## Удаление и поддержка

Удалите ConfigEntry Time Messenger через Settings > Devices & services. Home Assistant удалит локальные credentials, а integration очистит локальный dedupe state. Для Session integration также попытается выполнить logout в режиме best effort. Если logout не удался, завершите сессию вручную средствами tenant, если он это позволяет.

Подтвержденного remote revoke для OAuth и PAT нет, поэтому локальное удаление его не обещает. При необходимости отзовите token средствами вашего tenant.

Если проблема осталась, скачайте redacted diagnostics, проверьте tenant origin и служебные идентификаторы, затем откройте [issue tracker](https://github.com/dancingpizza/time-messenger-home-assistant/issues). Не прикладывайте tokens, passwords, MFA codes, Authorization headers или raw payload.
