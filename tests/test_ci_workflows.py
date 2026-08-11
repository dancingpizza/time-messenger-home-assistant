"""Static security and release-gate contracts for GitHub Actions workflows."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
WORKFLOWS = REPOSITORY_ROOT / ".github" / "workflows"
PINNED_ACTION = re.compile(r"^\s*-\s+uses:\s*[^@\s]+@[0-9a-f]{40}\s*#\s+.+$", re.MULTILINE)
EVENTS = ("pull_request:", "push:", "workflow_dispatch:")


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_every_release_workflow_covers_pr_branch_tag_and_manual_dispatch() -> None:
    for name in ("ci.yml", "hacs.yml", "hassfest.yml"):
        contents = workflow(name)
        assert "pull_request_target" not in contents
        assert all(event in contents for event in EVENTS)
        assert 'branches: ["**"]' in contents
        assert '"v*"' in contents


def test_workflows_have_read_only_permissions_and_immutable_action_pins() -> None:
    for name in ("ci.yml", "hacs.yml", "hassfest.yml"):
        contents = workflow(name)
        assert "permissions:\n  contents: read" in contents
        assert "permissions: write" not in contents
        assert PINNED_ACTION.search(contents), (
            f"{name} needs a pinned action with provenance comment"
        )
        for uses_line in (line for line in contents.splitlines() if "uses:" in line):
            assert re.search(r"@[0-9a-f]{40}\s+#", uses_line), uses_line


def test_ci_runs_the_canonical_locked_runtime_and_version_gates() -> None:
    contents = workflow("ci.yml")

    for command in (
        "uv sync --frozen --all-groups",
        "uv run --frozen pytest -q",
        "uv run --frozen ruff check .",
        "uv run --frozen ruff format --check .",
        "uv run --frozen mypy custom_components/time_messenger",
        "uv run --frozen python scripts/check_release_version.py",
    ):
        assert command in contents


def test_hacs_workflow_validates_integration_without_ignored_checks() -> None:
    contents = workflow("hacs.yml")

    assert "hacs/action@" in contents
    assert "category: integration" in contents
    assert "ignore" not in contents.lower()


def test_hassfest_workflow_uses_official_hassfest_validator() -> None:
    contents = workflow("hassfest.yml")

    assert "home-assistant/actions/hassfest@" in contents
