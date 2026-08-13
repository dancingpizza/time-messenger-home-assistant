# CLAUDE.md

Гид для AI-агентов, работающих в этом репозитории. Держи этот файл коротким
и актуальным — детали архитектуры и спеки живут в `docs/`, здесь только
ориентиры и правила, которые не выводятся из кода.

## Что это

Time Messenger — неофициальная custom-интеграция Home Assistant. Получает
личные сообщения из Time Messenger по WebSocket и публикует их как событие
Home Assistant (`time_messenger_event` и, с версии 0.0.3, нативная
`EventEntity`). Дистрибуция — HACS custom repository.

- Python `>=3.14.2`, Home Assistant `2026.8.1+` (см. `pyproject.toml`,
  `custom_components/time_messenger/manifest.json`).
- Код интеграции: `custom_components/time_messenger/`. Тесты:
  `tests/`. Release-скрипты: `scripts/`.

## Команды

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy custom_components/time_messenger
uv run python scripts/check_release_version.py
```

Это те же команды, что использует `.github/workflows/ci.yml` — перед тем как
считать задачу законченной, прогони их локально.

## Документация проекта

- [`docs/architecture.md`](docs/architecture.md) — источник истины по
  архитектуре: паттерн, инварианты (AD-1…AD-13), стек, структура кода.
  Обновляй в том же коммите, где меняется архитектурное решение.
- [`docs/specs/`](docs/specs/) — контракты уже реализованных фич (why /
  capabilities / constraints / non-goals), по одному файлу на срез работы,
  с датой в имени файла. Заводи новый файл для следующей значимой фичи,
  не редактируй задним числом старые контракты — фиксируй новое решение
  отдельно и, если оно меняет старое, отметь это в изменённом файле.
- [`docs/style-guide.md`](docs/style-guide.md) — голос и тон README и
  пользовательской документации.
- [`docs/superpowers/`](docs/superpowers/) — рабочие планы и design-доки,
  которые пишет установленный плагин-скилл `superpowers` при
  spec-driven разработке фичи. Это его namespace; не переноси туда контент
  вручную и не переименовывай — просто оставляй как есть.
- [`docs/index.html`](docs/index.html) — лендинг GitHub Pages
  (https://dancingpizza.github.io/time-messenger-home-assistant/), статический
  HTML без сборки. Не генерируется автоматически из README.

Раньше в репозитории был BMAD (`_bmad/`, `_bmad-output/`,
`.agents/skills/bmad-*`) — полный planning framework с собственными
агентами/воркфлоу. Он удалён; ценные архитектурные решения и спеки из его
вывода перенесены в `docs/architecture.md` и `docs/specs/` выше. История
всё ещё доступна в git при необходимости, но не как источник для новой
работы.

## Правила, которые не выводятся из кода

- **Секреты никогда не логируются.** Bearer-токены, пароли, MFA, client
  secret и заголовок Authorization не попадают в repr, diagnostics, events
  или обычные логи.
- **`message_text` по умолчанию скрыт** (`null`, `text_redacted: true`) —
  это privacy-контракт, а не временное упущение. Не включай передачу текста
  без явного user-facing opt-in.
- **Один способ авторизации без fallback.** OAuth, PAT и Session — три
  независимых пути; автоматическое переключение между ними запрещено (см.
  AD-3 в `docs/architecture.md`).
- **Fail-closed фильтрация.** Неизвестные payload, каналы или типы постов
  отбрасываются, а не обрабатываются «на всякий случай».
- **Версии синхронны.** `custom_components/time_messenger/manifest.json`,
  `pyproject.toml` и заголовок в `CHANGELOG.md` должны содержать одну и ту
  же версию — это проверяет `scripts/check_release_version.py`.
- **`docs/index.html` синхронизирован с README.** Это отдельный статический
  лендинг для GitHub Pages, не рендерится из README автоматически. Если
  правишь описание, возможности, ссылки на установку или примеры
  автоматизаций в README.md — перенеси то же изменение в `docs/index.html`
  в том же коммите.

## Релиз

Не создавай git tag, не пуши и не публикуй GitHub Release без отдельного
явного подтверждения пользователя в чате — это необратимые публичные
действия. Порядок и gates описаны в
[`docs/specs/2026-08-11-hacs-packaging.md`](docs/specs/2026-08-11-hacs-packaging.md).
