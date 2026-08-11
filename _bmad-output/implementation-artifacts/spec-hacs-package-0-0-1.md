---
title: 'HACS-пакет Time Messenger 0.0.1'
type: 'chore'
created: '2026-08-11'
status: 'done'
review_loop_iteration: 0
baseline_commit: '0595237649cbbcfe837f0a2e79363392c635ffb3'
context:
  - '{project-root}/_bmad-output/specs/spec-hacs-package-0-0-1/SPEC.md'
  - '{project-root}/_bmad-output/specs/spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Существующий runtime нельзя безопасно распространять через HACS: отсутствуют repository metadata, лицензия и changelog, а package version расходится с принятым первым release `0.0.1`.

**Approach:** Подготовить standard HACS directory package, синхронизировать release metadata и закрепить контракт packaging-тестами без изменения runtime.

## Boundaries & Constraints

**Always:** Реализовать только CAP-7 и CAP-9. Единственная integration directory — `custom_components/time_messenger`. `hacs.json` минимален. Manifest, package и changelog согласованы с `0.0.1`. Лицензия — MIT, `2026 dancingpizza`. Существующие runtime metadata сохраняются.

**Ask First:** Любое изменение copyright holder, repository URL, минимальной версии Home Assistant, package layout или release version.

**Never:** Не менять runtime, auth, event schema, README, icon или CI. Запрещены HACS keys `content_in_root`, `zip_release`, `filename`, `persistent_directory`, `country`, а также push, tag и GitHub Release.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HACS layout | Одна integration | Минимальный `hacs.json`; устанавливается только `time_messenger` | Test отклоняет второй component/forbidden key |
| Version | Manifest/package/changelog | Везде `0.0.1`; tag contract `v0.0.1` | Test отклоняет drift/нет heading |
| Metadata | Текущий manifest | Repository docs, issues, `@dancingpizza`; прочие keys сохранены | Exact assertions fail closed |
| Legal/release | Файлы отсутствуют | Полный MIT и release notes с limitations/migration | Test отклоняет отсутствие |

</frozen-after-approval>

## Code Map

- `custom_components/time_messenger/manifest.json:1` — обновить version/codeowner/URLs; остальные keys сохранить.
- `pyproject.toml:1` — заменить только project version.
- `hacs.json` — новый root HACS contract.
- `LICENSE`, `CHANGELOG.md` — MIT и release entry `0.0.1`.
- `tests/components/time_messenger/test_packaging.py` — новые `Path`/`json`/`tomllib` contract tests.
- Остальной `custom_components/time_messenger/**` — read-only.

## Tasks & Acceptance

**Execution:**
- [x] `tests/components/time_messenger/test_packaging.py` — RED для layout, metadata, MIT и parity.
- [x] `hacs.json`, manifest, `pyproject.toml` — GREEN для HACS contract и `0.0.1`.
- [x] `LICENSE`, `CHANGELOG.md` — добавить MIT и содержательный release entry.
- [x] Полный test/lint/type suite — проверить runtime regression.

**Acceptance Criteria:**
- Given repository checkout, when packaging tests run, then layout и metadata соответствуют CAP-7 без forbidden keys.
- Given version `0.0.1`, when parity test читает три release surfaces, then значения совпадают с tag contract `v0.0.1`.
- Given existing runtime, when build завершён, then прежние tests/Ruff/mypy зелёные и remote state не изменён.

## Spec Change Log

## Verification

**Commands:**
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run pytest` — packaging и behavior green.
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run ruff check . && UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run ruff format --check .` — lint/format clean.
- `UV_CACHE_DIR=/tmp/syncer-ha-uv-cache uv run mypy custom_components/time_messenger` — typing clean.
- `git diff --check` — patch hygiene clean.

## Suggested Review Order

**Distribution contract**

- Manifest связывает HACS package с repository, maintainer и версией.
  [`manifest.json:4`](../../custom_components/time_messenger/manifest.json#L4)

- Минимальный HACS descriptor сохраняет standard directory installation.
  [`hacs.json:1`](../../hacs.json#L1)

**Release identity и legal**

- Package metadata фиксирует единую release version `0.0.1`.
  [`pyproject.toml:1`](../../pyproject.toml#L1)

- Changelog документирует первый выпуск, ограничения и отсутствие migration.
  [`CHANGELOG.md:3`](../../CHANGELOG.md#L3)

- Полный MIT license фиксирует разрешённые условия распространения.
  [`LICENSE:1`](../../LICENSE#L1)

**Regression contract**

- Packaging tests защищают layout, metadata, lockfile parity и MIT text.
  [`test_packaging.py:50`](../../tests/components/time_messenger/test_packaging.py#L50)
