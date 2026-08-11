"""Contract tests for the standalone release-version checker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).parents[1]
CHECKER = REPOSITORY_ROOT / "scripts" / "check_release_version.py"


def write_release_surfaces(root: Path, *, version: str = "0.0.1") -> None:
    """Create the smallest hermetic repository accepted by the checker."""
    manifest = root / "custom_components" / "time_messenger" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"version": version}), encoding="utf-8")
    (root / "pyproject.toml").write_text(f"[project]\nversion = {version!r}\n", encoding="utf-8")
    (root / "uv.lock").write_text(
        f"[[package]]\nname = 'time-messenger-home-assistant'\nversion = {version!r}\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(f"## [{version}] - 2026-08-11\n", encoding="utf-8")


def run_checker(
    root: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), *arguments],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def test_checker_accepts_green_repository_parity_and_matching_tag(tmp_path: Path) -> None:
    write_release_surfaces(tmp_path)

    result = run_checker(tmp_path, "--tag", "v0.0.1")

    assert result.returncode == 0
    assert "parity passed: 0.0.1" in result.stdout


@pytest.mark.parametrize(
    ("path", "replacement", "surface"),
    [
        ("custom_components/time_messenger/manifest.json", '"0.0.2"', "manifest.json"),
        ("pyproject.toml", "0.0.2", "pyproject.toml"),
        ("uv.lock", "0.0.2", "uv.lock project entry"),
        ("CHANGELOG.md", "0.0.2", "CHANGELOG.md heading"),
    ],
)
def test_checker_blocks_intentional_version_drift(
    tmp_path: Path, path: str, replacement: str, surface: str
) -> None:
    write_release_surfaces(tmp_path)
    target = tmp_path / path
    target.write_text(
        target.read_text(encoding="utf-8").replace("0.0.1", replacement),
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert surface in result.stderr


@pytest.mark.parametrize(
    ("path", "contents", "surface"),
    [
        ("custom_components/time_messenger/manifest.json", "{}", "manifest.json"),
        ("pyproject.toml", "[project]\nversion = 'version-one'\n", "pyproject.toml"),
        (
            "uv.lock",
            "[[package]]\nname = 'different-project'\nversion = '0.0.1'\n",
            "uv.lock project entry",
        ),
        ("CHANGELOG.md", "# Changelog\n", "CHANGELOG.md heading"),
    ],
)
def test_checker_blocks_missing_or_invalid_release_values(
    tmp_path: Path, path: str, contents: str, surface: str
) -> None:
    write_release_surfaces(tmp_path)
    (tmp_path / path).write_text(contents, encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert surface in result.stderr


def test_checker_blocks_duplicate_project_entries_in_lockfile(tmp_path: Path) -> None:
    write_release_surfaces(tmp_path)
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text(
        lockfile.read_text(encoding="utf-8")
        + "\n[[package]]\nname = 'time-messenger-home-assistant'\nversion = '0.0.1'\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "uv.lock project entry" in result.stderr
    assert "expected exactly one package entry" in result.stderr
    assert "found 2" in result.stderr


def test_checker_reports_malformed_text_surface_without_traceback(tmp_path: Path) -> None:
    write_release_surfaces(tmp_path)
    (tmp_path / "CHANGELOG.md").write_bytes(b"\xff")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "CHANGELOG.md heading" in result.stderr
    assert "Traceback" not in result.stderr


def test_explicit_tag_takes_priority_over_github_tag_environment(tmp_path: Path) -> None:
    write_release_surfaces(tmp_path)

    result = run_checker(
        tmp_path,
        "--tag",
        "v0.0.1",
        environment={"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v9.9.9"},
    )

    assert result.returncode == 0


def test_checker_ignores_github_ref_name_outside_tag_context(tmp_path: Path) -> None:
    write_release_surfaces(tmp_path)

    result = run_checker(
        tmp_path,
        environment={"GITHUB_REF_TYPE": "branch", "GITHUB_REF_NAME": "v0.0.2"},
    )

    assert result.returncode == 0


def test_checker_uses_github_tag_only_for_tag_context(tmp_path: Path) -> None:
    write_release_surfaces(tmp_path)

    result = run_checker(
        tmp_path, environment={"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v0.0.2"}
    )

    assert result.returncode == 1
    assert "tag" in result.stderr


@pytest.mark.parametrize("tag", ["0.0.1", "v0.0.2", "release-0.0.1"])
def test_checker_blocks_nonmatching_or_malformed_release_tag(tmp_path: Path, tag: str) -> None:
    write_release_surfaces(tmp_path)

    result = run_checker(tmp_path, "--tag", tag)

    assert result.returncode == 1
    assert "tag" in result.stderr
