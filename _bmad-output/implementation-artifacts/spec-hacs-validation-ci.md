---
title: 'Автоматическая проверка HACS release readiness'
type: 'feature'
created: '2026-08-11'
status: 'done'
review_loop_iteration: 0
baseline_commit: '35345b7bd1869a573e261890beae0a60a8c418ed'
context:
  - '_bmad-output/specs/spec-hacs-validation-ci/SPEC.md'
  - '_bmad-output/specs/spec-syncer-time-messenger-t-bank-home-assist/distribution-release.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Репозиторий версии 0.0.1 не имеет воспроизводимых CI gates, поэтому version drift, invalid HACS metadata или несовместимость с Home Assistant могут обнаружиться только после публикации.

**Approach:** Добавить локальный tag-aware version checker, негативные contract tests и три минимально привилегированных GitHub Actions workflow для runtime gates, HACS Action и Hassfest. После завершения этого SPEC пользователь отдельно разрешил push, tag `v0.0.1` и GitHub Release, но release automation в repository не добавляется.

## Boundaries & Constraints

**Always:** На pull request, branch push, tag `v*` и manual dispatch запускать соответствующие gates. Local CI использует locked dependencies и канонические pytest, Ruff, format и mypy команды. Version checker сравнивает manifest, pyproject, project entry в uv.lock и changelog heading; в tag context требует `v<version>`, но игнорирует event `schema_version`. Third-party actions закреплены immutable SHA или фиксированным release, permissions минимальны, HACS category равна `integration`, ignores отсутствуют. Live tenant probe и clean HACS install остаются честно обозначенными external gates.

**Ask First:** Изменение версии 0.0.1, runtime/auth/event contracts, repository settings или добавление release automation. Публикация разрешена только после зелёного reviewed commit; если remote CI, auth или exact tag target не подтверждены, остановиться до исправления.

**Never:** Использовать `pull_request_target`, передавать tenant secrets в CI, скрывать HACS errors через `ignore`, объявлять live probe/install smoke пройденными без факта, добавлять zip packaging, default-HACS submission или менять CAP-1–CAP-9 и AD-1–AD-13.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Branch или PR | Все version surfaces равны 0.0.1 | Checker и local gates завершаются успешно без требования tag | Любой drift или invalid SemVer дает nonzero с названием surface |
| Release tag | Tag `v0.0.1` указывает на green commit | Checker принимает exact tag и workflows запускают все required jobs | Missing `v`, другая версия или branch mismatch блокируют release |
| Changelog/lock drift | Одна surface изменена или entry отсутствует | Негативный test доказывает deterministic failure | Checker не изменяет файлы и не подменяет expected value |
| HACS/Hassfest | Workflow запущен на поддерживаемом событии | Category integration, no ignores, metadata/translations проверяются official actions | Upstream failure остается видимым и блокирует publication |
| External gates | Нет tenant credentials или release еще не опубликован | CI явно не симулирует probe/install smoke | Gate остается pending release evidence, а не success |

</frozen-after-approval>

## Code Map

- `scripts/check_release_version.py` -- новый stdlib-only checker с `--root`, `--tag` и GitHub tag environment boundary.
- `tests/test_release_version.py` -- green parity и isolated tmp-path failures для drift, malformed/missing version и tag mismatch.
- `tests/test_ci_workflows.py` -- статический contract событий, commands, permissions, action pins, HACS category/no-ignore и Hassfest presence.
- `.github/workflows/ci.yml` -- checkout, locked uv environment, pytest, Ruff, format, mypy и version parity.
- `.github/workflows/hacs.yml` -- official HACS validation без ignored checks.
- `.github/workflows/hassfest.yml` -- Home Assistant metadata/translation validation.
- `tests/components/time_messenger/test_packaging.py:test_release_version_is_identical_on_every_release_surface` -- существующая hard-coded проверка; сохранить, checker делает tag-aware contract.
- `custom_components/time_messenger/manifest.json`, `pyproject.toml`, `uv.lock`, `CHANGELOG.md` -- read-only version surfaces 0.0.1.

## Tasks & Acceptance

**Execution:**
- [x] `tests/test_release_version.py` -- RED matrix создан для valid parity, intentional drift, invalid/missing values и matching/mismatching tags; после реализации checker тесты GREEN.
- [x] `scripts/check_release_version.py` -- реализован deterministic reusable checker без сторонних dependencies и file mutation.
- [x] `tests/test_ci_workflows.py` -- зафиксирован workflow security/event/gate contract.
- [x] `.github/workflows/ci.yml` -- реализованы locked runtime и version gates с read-only permissions.
- [x] `.github/workflows/hacs.yml` и `.github/workflows/hassfest.yml` -- добавлены pinned official validators на PR/push/tags/manual dispatch.
- [x] `_bmad-output/implementation-artifacts/spec-hacs-validation-ci.md` -- tasks отмечены; RED/GREEN, pin provenance и external-gate evidence записаны ниже.

**Acceptance Criteria:**
- Given clean repository 0.0.1, when local checker и полный suite запущены, then все release surfaces совпадают и gates проходят.
- Given любая version surface или tag намеренно расходится, when checker/test запущен, then publication блокируется понятным nonzero result.
- Given workflow definitions, when security contract test их проверяет, then events, immutable pins, minimal permissions, no-ignore HACS и Hassfest присутствуют.
- Given reviewed green commit, when post-build publication начинается, then push идет в remote `main`, annotated `v0.0.1` указывает на тот же commit, а GitHub Release создается только после успешных remote checks.

## Spec Change Log

- 2026-08-11: RED/GREEN — добавлены hermetic negative contract tests для version drift,
  malformed/missing surfaces и tag contexts; checker и CI workflow contracts реализованы.
- 2026-08-11: Pin provenance — `actions/checkout` v4.2.2 закреплён на
  `11bd71901bbe5b1630ceea73d27597364c9af683`; `astral-sh/setup-uv` v6.0.1 — на
  `b75a909f75acd358c2196fb9a5f1299a92742213`; `hacs/action` 22.5.0 — на
  `d556e736723344f83838d08488c983a15381059a`; Hassfest — на проверенный snapshot
  `home-assistant/actions` master `a7c616ce81ccda50150bf1595786c71b1883fabb`.
- 2026-08-11: External-gate evidence — live tenant probe и clean HACS install smoke
  не выполнялись и не объявляются успешными: они требуют tenant credentials и
  опубликованный GitHub Release соответственно.
- 2026-08-11: Review evidence — checker игнорирует `GITHUB_REF_NAME` вне tag
  context, требует ровно один project entry в `uv.lock` и возвращает named
  nonzero diagnostic для duplicate/unreadable release surfaces без traceback.

## Design Notes

Checker получает repository root явно для hermetic tmp-path tests. `--tag` имеет приоритет; иначе tag читается только при `GITHUB_REF_TYPE=tag`. Workflow comments сохраняют human-readable action version рядом с immutable SHA.

## Verification

**Commands:**
- `uv run --frozen pytest -q` -- полный suite зеленый без скрытых failures.
- `uv run --frozen ruff check .` -- lint зеленый.
- `uv run --frozen ruff format --check .` -- format зеленый.
- `uv run --frozen mypy custom_components/time_messenger` -- strict source types зеленые.
- `uv run --frozen python scripts/check_release_version.py --tag v0.0.1` -- release parity успешна.
- `uv run --frozen python scripts/check_release_version.py --tag v0.0.2` -- ожидаемый nonzero intentional drift.
- `git diff --check` -- whitespace чистый.

**Manual checks:**
- Проверить provenance pinned action commits и отсутствие secrets, write permissions, ignores и fake external-gate success.

## Suggested Review Order

**Версионная граница**

- Checker связывает package surfaces с release tag без изменения файлов.
  [`check_release_version.py:28`](../../scripts/check_release_version.py#L28)

- Tag context учитывается только для GitHub tag ref.
  [`check_release_version.py:79`](../../scripts/check_release_version.py#L79)

**Runtime CI**

- Locked environment запускает все канонические локальные release gates.
  [`ci.yml:1`](../../.github/workflows/ci.yml#L1)

**Внешние валидаторы**

- HACS проверяет integration без скрытых ignores.
  [`hacs.yml:1`](../../.github/workflows/hacs.yml#L1)

- Hassfest проверяет integration metadata и translations на pinned action.
  [`hassfest.yml:1`](../../.github/workflows/hassfest.yml#L1)

**Контрактные тесты**

- Hermetic tests доказывают parity, drift и tag-boundary behavior.
  [`test_release_version.py:47`](../../tests/test_release_version.py#L47)

- Workflow tests защищают события, permissions, pins и required gates.
  [`test_ci_workflows.py:18`](../../tests/test_ci_workflows.py#L18)
