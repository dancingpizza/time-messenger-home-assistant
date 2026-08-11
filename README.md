# Time Messenger для Home Assistant

Неофициальная интеграция, которая передает новые личные сообщения из Time Messenger в Home Assistant. Полученные события можно использовать в автоматизациях: показывать уведомления, мигать светом или озвучивать текст.

Поддерживается Home Assistant 2026.8.1 и новее.

## Возможности

- Получает новые личные сообщения от других пользователей.
- Создаёт сущность события «Личное сообщение» для редактора автоматизаций.
- Сохраняет совместимость с событием `time_messenger_event`.
- По умолчанию скрывает текст сообщения.

Групповые чаты и сообщения, полученные во время отключения Home Assistant, пока не поддерживаются.

## Установка

1. Откройте [Time Messenger в HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=dancingpizza&repository=time-messenger-home-assistant&category=integration).
2. Установите интеграцию и перезапустите Home Assistant.
3. Перейдите в Settings > Devices & services > Add integration.
4. Найдите Time Messenger и следуйте подсказкам на экране.

Если ссылка не открывается, добавьте `dancingpizza/time-messenger-home-assistant` в HACS как пользовательский репозиторий категории Integration.

Для ручной установки скопируйте каталог `custom_components/time_messenger` в `custom_components` вашей конфигурации Home Assistant и перезапустите Home Assistant.

## Подключение

Укажите адрес сервера Time, например `https://time.example.org`, и выберите доступный способ входа. Организация может поддерживать OAuth, персональный токен или обычный логин с паролем.

После подключения появится устройство учётной записи Time Messenger и сущность события «Личное сообщение». Не путайте её с сущностью `Update`: `Update` принадлежит HACS и сообщает только о новых версиях интеграции.

Текст сообщений по умолчанию скрыт. Его можно включить в Settings > Devices & services > Time Messenger > Configure. После включения текст будет доступен автоматизациям Home Assistant.

## Автоматизация через интерфейс

1. Откройте Settings > Automations & scenes и создайте автоматизацию.
2. В разделе «Когда» нажмите «Добавить триггер».
3. Найдите триггер «Событие: Получено событие».
4. Выберите сущность Time Messenger «Личное сообщение».
5. Выберите тип «Получено личное сообщение».
6. Добавьте нужное действие: уведомление, свет, озвучивание или другое действие Home Assistant.

В YAML та же автоматизация выглядит так. `event.time_messenger_direct_message` — стандартный ID первой учётной записи; если вы переименовали сущность или добавили несколько аккаунтов, выберите свой ID в интерфейсе.

```yaml
alias: Time Messenger, новое личное сообщение
triggers:
  - trigger: event.received
    target:
      entity_id: event.time_messenger_direct_message
    options:
      event_type:
        - direct_message
actions:
  - action: persistent_notification.create
    data:
      title: Time Messenger
      message: >-
        {{ trigger.to_state.attributes.message_text
           or ('Новое сообщение от '
               ~ (trigger.to_state.attributes.sender_username
                  | default(trigger.to_state.attributes.sender_user_id, true))) }}
mode: queued
```

Данные сообщения находятся в `trigger.to_state.attributes`. Доступны идентификаторы отправителя, канала и сообщения, время создания, сведения о вложениях и — только после включения настройки приватности — `message_text`.

## Совместимость со старыми автоматизациями

Событие шины `time_messenger_event` продолжает работать без изменений. Существующие автоматизации обновлять необязательно:

```yaml
triggers:
  - trigger: event
    event_type: time_messenger_event
```

## Поддержка

Если интеграция не работает, откройте [issue](https://github.com/dancingpizza/time-messenger-home-assistant/issues) и опишите проблему. Не публикуйте пароли, токены и текст личных сообщений.
