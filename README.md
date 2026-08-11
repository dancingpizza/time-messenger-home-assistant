# Time Messenger для Home Assistant

Неофициальная интеграция, которая передает новые личные сообщения из Time Messenger в Home Assistant. Полученные события можно использовать в автоматизациях: показывать уведомления, мигать светом или озвучивать текст.

Поддерживается Home Assistant 2026.8.1 и новее.

## Возможности

- Получает новые личные сообщения от других пользователей.
- Создает событие `time_messenger_event` в Home Assistant.
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

Текст сообщений по умолчанию скрыт. Его можно включить в Settings > Devices & services > Time Messenger > Configure. После включения текст будет доступен автоматизациям Home Assistant.

## Пример автоматизации

Эта автоматизация показывает постоянное уведомление. Если передача текста выключена, в уведомлении будет указан отправитель.

```yaml
alias: Time Messenger, новое личное сообщение
triggers:
  - trigger: event
    event_type: time_messenger_event
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

Другие действия можно настроить обычными средствами Home Assistant.

## Поддержка

Если интеграция не работает, откройте [issue](https://github.com/dancingpizza/time-messenger-home-assistant/issues) и опишите проблему. Не публикуйте пароли, токены и текст личных сообщений.
