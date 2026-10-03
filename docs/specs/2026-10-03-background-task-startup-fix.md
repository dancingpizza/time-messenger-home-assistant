# Исправление задержки запуска Time Messenger

## Причина

Журнал рабочего Home Assistant показывает startup timeout, ожидающий
`_async_supervise`, `_async_health_loop` и `_async_keep_online_loop`.
Эти циклы живут до unload, но были созданы через `hass.async_create_task()`:
Home Assistant включал их в ожидание конечных setup-задач. Это задерживало
общий старт примерно на пять минут даже при исправной сети и авторизации.

## Решение и границы

Все три цикла запускаются через публичный
`ConfigEntry.async_create_background_task(hass, coroutine, name)`.
Сохраняются runtime generation guard, отмена и ожидание задач, закрытие
WebSocket и освобождение принадлежащей entry сессии. Фоновые задачи также
отменяются Home Assistant при shutdown и выгрузке ConfigEntry.
Identity/capability gate перед запуском остаётся конечным и ожидаемым.
Сетевые retry, классификация ошибок, авторизация, события и privacy не меняются.

Увеличение startup timeout только скрывает проблему. Перенос запуска на событие
started оставляет неверный тип задач. Обычный `asyncio.create_task()` убрал бы
интеграцию с lifecycle HA. Поэтому выбран штатный entry-owned background API.

## Проверка

Регрессионный тест использует настоящий Home Assistant 2026.8.1 и ConfigEntry,
блокируя только сетевой listener. Пока listener и включённые optional loops
живы, `hass.async_block_till_done()` должен завершаться. После unload все
созданные задачи должны быть отменены. Проверяются четыре сочетания health и
presence. До исправления все четыре случая воспроизводят TimeoutError.
Полный набор тестов дополнительно проверяет idempotent start, reauth,
reconnect, остановку и generation guards.

Исправление включено в 0.0.7. После установки требуется перезапуск
Home Assistant. Локальные тесты не заменяют проверку времени старта на сервере:
нужно подтвердить loaded-состояние entry, работающие фоновые циклы и отсутствие
startup timeout, ожидающего Time Messenger.
