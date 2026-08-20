# Спека: поддержание статуса «В сети» по недельному расписанию

Статус: реализовано, релиз `0.0.6` (2026-08-20).

Дополняет исходную спеку интеграции и точечно изменяет старое ограничение
«REST только для checks/metadata»: единственный новый side effect — описанный
ниже status PUT. Non-goal «исходящие сообщения Home Assistant → Time» остаётся
в силе; integration по-прежнему не создаёт посты.

## Зачем

Time автоматически переводит неактивного пользователя в статус «Отошёл».
Пользователю интеграции нужен явный opt-in режим, который в рабочие часы
периодически возвращает личную учётную запись в статус `online`, но не делает
никаких специальных status-запросов вечером, ночью или в выходные.

Функция экспериментальная: официальный Time API умеет установить `online`, но
не документирует отдельный presence heartbeat и не обещает закрепить этот
статус навсегда. Поэтому интеграция описывает только собственное расписание
запросов, а не гарантирует, как долго конкретный tenant будет показывать
результат каждого запроса.

## Пользовательский контракт

Функция выключена по умолчанию. В
`Settings > Devices & services > Time Messenger > Configure` пользователь
настраивает:

- включение поддержания статуса;
- один или несколько дней недели;
- локальное время начала и окончания;
- целый интервал обновления от 1 до 60 минут.

Значения по умолчанию после включения: понедельник–пятница, `09:00:00`–
`18:00:00`, один запрос раз в 4 минуты. Четыре минуты оставляют запас
относительно распространённого server-side away timeout в 300 секунд, но
администратор tenant может настроить другое значение.

Расписание использует часовой пояс Home Assistant:

- окно полуоткрытое: начало включено, окончание исключено — `[start, end)`;
- если окончание позже начала, окно заканчивается в тот же день;
- если окончание раньше начала, окно продолжается через полночь, а выбранный
  weekday означает день **начала**. Например, пятница `22:00`–`06:00`
  включает субботу с `00:00` до `06:00`;
- одинаковые начало и окончание запрещены, чтобы случайно не получить
  неоднозначный круглосуточный режим;
- при запуске Home Assistant внутри окна первый запрос выполняется сразу;
  вне окна task ждёт следующего открытия и не обращается к Time;
- после окончания окна интеграция не выставляет `away` или `offline`. Последний
  `online` может быть виден ещё некоторое время, пока сам Time не пересчитает
  присутствие.

При смене options `OptionsFlowWithReload` перезагружает ConfigEntry: прежняя
task отменяется, а новый runtime получает целиком новое immutable-расписание.

## Time API contract

Внутри активного окна выполняется authenticated запрос на bound origin:

```http
PUT /api/v4/users/me/status
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": "<bound_user_id>",
  "status": "online"
}
```

Успех принимается только при `2xx` JSON-object, в котором `user_id` совпадает
с identity, зафиксированной во время setup, а `status == "online"`. Пустой,
malformed или противоречащий ответ не считается подтверждением.

Identity захватывается один раз после setup gate. Фоновая task не читает
изменяемый `ConfigEntry.data` на каждой итерации: token-only OAuth update или
сторонняя мутация entry не могут незаметно перенаправить status-запрос к другой
identity.

Официальное описание endpoint предупреждает, что установка `online` возвращает
статус к автоматическому обновлению на основе активности, а не фиксирует его
навсегда. В документации endpoint также указано permission
`edit_other_users`; отдельное исключение для собственного `me` не описано.
Поэтому фактическую доступность нужно подтвердить на целевом tenant:
[Update user status](https://docs.time-messenger.ru/api/v4/update-user-status/),
[OpenAPI schema](https://docs.time-messenger.ru/api/v4/%D1%81%D1%85%D0%B5%D0%BC%D0%B0/).

## Runtime и расписание

Загруженная ConfigEntry владеет тремя независимыми задачами:

1. supervised WebSocket listener;
2. auth health-check раз в 15 минут;
3. optional online keeper с пользовательским расписанием.

Keeper отделён от health-check: у них разные интервалы, side effects и
классификация ошибок. Он использует ту же runtime generation. Unload,
options reload, подтверждённый auth failure или terminal WebSocket capability
failure сначала инвалидируют generation и отменяют все entry-owned tasks, а
затем закрывают socket и освобождают session. Late callback старой generation
не выполняет новый PUT и не создаёт reauth.

После каждой попытки task ждёт полный настроенный интервал. Если ожидание
пересекает конец окна, следующая итерация сначала проверяет расписание и не
делает запрос снаружи. Полная задержка принципиальна и для `Retry-After`: её
нельзя забыть из-за короткого неактивного промежутка между двумя окнами.
После потенциально долгого получения или OAuth refresh токена окно проверяется
ещё раз непосредственно перед `session.request`. Если за это время наступил
exclusive end, status PUT подавляется. Если уже отправленный внутри окна PUT
завершился после его окончания, полный cadence/`Retry-After` всё равно
сохраняется; новый PUT снаружи не начинается.
Снаружи окна локальная проверка времени выполняется не реже раза в минуту;
это не сетевой вызов и позволяет быстро учесть смену wall clock или timezone.

### DST

Расчёт границ выполняется в часовом поясе aware-datetime, который передаёт
Home Assistant, а длительности считаются через UTC:

- в повторяющийся осенний час начало использует первый `fold`, окончание —
  второй, чтобы окно оставалось непрерывным;
- несуществующее весеннее время нормализуется вперёд на величину UTC-offset
  gap с сохранением минут и секунд: `02:30` становится `03:30` при часовом
  переходе;
- задержки остаются конечными и положительными, включая переход недели
  воскресенье → понедельник.

Это явная семантика интеграции, а не обещание полного совпадения со всеми
вариантами scheduler UI Home Assistant.

## Классификация ошибок

| Результат | Поведение |
| --- | --- |
| Подтверждённый `2xx` | Issue прежнего сбоя удаляется; следующий PUT не раньше настроенного интервала и только внутри окна. |
| `401`, identity mismatch из auth-health `GET /users/me`, terminal OAuth refresh | Общая generation инвалидируется, listener/health/keeper останавливаются, ConfigEntry проходит стандартный reload → `ConfigEntryAuthFailed` → reauth. |
| `403` / `UnsupportedCapability` | Keeper останавливается; сообщения и auth health продолжают работать. Создаётся persistent Repairs warning `keep_online_unavailable`. |
| `400`, `404`, malformed или неподтверждённый `2xx` | Считается постоянным protocol/capability failure: keeper останавливается и создаёт тот же warning, без ложного reauth. |
| `429` | Keeper остаётся жив; следующая попытка ждёт не меньше обычного интервала и bounded `Retry-After`/rate-limit reset, даже если задержка пересекает границу окна. |
| DNS, timeout, `5xx`, transient OAuth refresh | Message listener не затрагивается; повтор не раньше следующего настроенного интервала и только внутри окна. |
| Неожиданное исключение optional task | Не раскрывается пользователю как auth failure; повторяется по тому же безопасному cadence. |
| Повреждённые stored options | Fail-closed: keeper не запускается, status API не вызывается, создаётся `keep_online_unavailable`; получение сообщений остаётся активным. |

При opt-out и при удалении ConfigEntry entry-scoped warning удаляется. После
исправления server capability он снимается только первым подтверждённым PUT,
поэтому reload с всё ещё неработающим API не скрывает проблему преждевременно.

## Почему не сообщения самому себе

В OpenAPI создание поста имеет `set_online=true`, но схема
«создать сообщение → удалить» отвергнута:

- `DELETE /posts/{post_id}` выполняет soft delete, а не физическое удаление;
- цикл раз в 5 минут создаёт 105 120 soft-deleted posts в год;
- create/delete могут оставаться в audit/compliance/backup и расходятся по
  WebSocket на клиентские устройства;
- сбой удаления оставляет видимое сообщение;
- ровно пять минут совпадают со стандартным away timeout и не оставляют
  запаса на scheduler/network delay.

Прямой status endpoint делает одну mutation без контента и без post lifecycle.
Также отвергнуты:

- WebSocket action `update_presence` — он выбирает канал/ветку для событий
  `typing`, а не глобальный online;
- открытый WebSocket или `GET /users/me` health-check — Time не документирует
  их как пользовательскую presence activity;
- принудительный `offline` в конце окна — пользователь просил прекратить
  специальные запросы, а не менять его настоящий статус;
- объединение с auth health task — side-effecting PUT не должен менять
  независимый read-only cadence проверки credentials.

Официальные основания:
[Create post](https://docs.time-messenger.ru/api/v4/create-post/),
[Delete post](https://docs.time-messenger.ru/api/v4/delete-post/),
[WebSocket API](https://docs.time-messenger.ru/api/v4/%D0%B2%D0%B5%D0%B1-%D1%81%D0%BE%D0%BA%D0%B5%D1%82-api/),
[away timeout](https://docs.time-messenger.ru/administration/settings/experimental/features/).

## Пользовательские последствия и безопасность

Каждый PUT использует существующий redirect-refusing HTTPS adapter и общий
TokenProvider. Bearer, response body и Authorization header не попадают в
logs, events, diagnostics или Repairs.

Функция может отменять вручную выбранные `DND`, `away` или `offline` и влиять
на мобильные уведомления, правила которых зависят от presence. Это явно
показано в options UI; скрытого включения или миграции existing entries нет.

Diagnostics содержат только несекретные options и boolean
`keep_online_running`: дни, границы, интервал и состояние task. Они не содержат
token, историю status response или личные сообщения.

## Проверка реализации

Автоматические тесты фиксируют как минимум:

- opt-in default `false`, Mon–Fri `09:00`–`18:00`, interval 4 минуты;
- один или несколько weekday, целый interval `1..60`, запрет одинаковых границ;
- exact start/end, weekend, week wrap и overnight previous-day semantics;
- DST gap/fold и расчёт elapsed seconds через UTC;
- immediate PUT внутри окна и отсутствие PUT снаружи;
- повторная проверка окна после token refresh и подавление late PUT;
- lifecycle/cancellation третьей task и generation guard;
- bound identity в URL/body/response и отсутствие динамической смены identity;
- `401` использует общий reauth path;
- `403`/protocol failure останавливает только keeper и создаёт warning;
- transient/`429` сохраняют listener и соблюдают cadence/`Retry-After`;
- opt-out/removal/success очищают entry-scoped issue;
- diagnostics остаются allowlisted и не раскрывают secrets.

Нужен live tenant probe: подтвердить право собственного аккаунта на
`PUT /users/me/status`, форму ответа, реальный away timeout и влияние на
DND/push. Unit-тесты не подменяют этот внешний gate. Для `0.0.6` владелец
принял ограниченное release exception: функция публикуется выключенной по
умолчанию и явно экспериментальной до такой проверки. Gate остаётся
непройденным; снимать предупреждение или обещать постоянный online нельзя.
