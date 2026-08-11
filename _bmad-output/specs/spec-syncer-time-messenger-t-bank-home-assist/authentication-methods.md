# Способы авторизации Time

Каждый способ представляет персональную Time identity и реализует единый `TokenProvider` из AD-3. Пользователь выбирает mode для конкретной ConfigEntry; автоматическое переключение запрещено.

| Способ | Настройка и хранение | Проверка и обновление | Unsupported / reauth |
| --- | --- | --- | --- |
| OAuth | Application Credential получает `auth_domain`, равный normalized tenant origin; custom implementation строит same-origin `/oauth/authorize` и `/oauth/access_token`. ConfigEntry хранит OAuth token, а client credentials принадлежат Home Assistant `application_credentials`. Используется authorization code; implicit grant запрещён. | После выдачи или refresh `GET /api/v4/users/me` подтверждает identity, затем WebSocket получает `hello`. Refresh выполняется средствами OAuth adapter. | Нужны tenant client registration, scopes, PKCE policy и точный HA redirect URI. Terminal refresh failure запускает reauth того же mode. |
| PAT | Пользователь вставляет созданный им PAT; он хранится как bearer в `ConfigEntry.data`. | `users/me` и WebSocket `hello` проходят с тем же bearer; PAT действует до отзыва. | Администратор может отключить PAT; `401` запускает PAT reauth. Интеграция не предлагает другой mode автоматически. |
| Session | Config flow отправляет `login_id`, password и optional MFA в `POST /api/v4/users/login`; сохраняется только ответный header `Token`, password/MFA не сохраняются. | Ответный user и последующий `users/me` должны совпасть; WebSocket работает до завершения сессии. | Истечение/отзыв запускает session reauth. Если login endpoint запрещён SSO policy, mode показывается unsupported до появления документированного tenant flow; browser-login emulation запрещена. |

## Общий security и lifecycle contract

- Bearer, password, MFA, client secret и Authorization header не попадают в events, diagnostics, repr и обычные logs.
- Authenticated REST/WSS не следует redirects и не передаёт bearer за пределы bound tenant origin.
- До runtime каждый mode проходит общий `users/me` identity check и WebSocket `hello`; пара tenant origin + `user_id` становится unique identity ConfigEntry.
- Ошибка одного mode не инициирует fallback или downgrade на другой.
- Transient network errors остаются в retry; auth errors запускают reauth; административно отключённый mode отображается как unsupported.
- Unload сохраняет credentials и только останавливает runtime. Удаление ConfigEntry очищает локальные OAuth/bearer данные и dedupe Store; session выполняет best-effort logout. OAuth/PAT remote revoke выполняется только через подтверждённый tenant endpoint.
- Target-tenant acceptance probe обязан проверить каждый из трёх mode, который включён администратором.
