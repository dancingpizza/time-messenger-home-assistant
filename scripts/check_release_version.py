#!/usr/bin/env python3
"""Validate that every release-version surface describes one SemVer release."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import NoReturn

SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def fail(message: str) -> NoReturn:
    """Print a stable failure message and stop publication gates."""
    print(f"release version check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_version(path: Path, surface: str, loader: object) -> str:
    """Load one version value while keeping its surface named in errors."""
    try:
        version = loader(path)
    except (
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        StopIteration,
        tomllib.TOMLDecodeError,
        ValueError,
    ) as error:
        fail(f"{surface}: {error}")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        fail(f"{surface}: expected a valid SemVer version, got {version!r}")
    return version


def manifest_version(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def project_version(path: Path) -> object:
    with path.open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def lock_version(path: Path) -> object:
    with path.open("rb") as file:
        packages = tomllib.load(file)["package"]
    matching_packages = [
        package for package in packages if package["name"] == "time-messenger-home-assistant"
    ]
    if len(matching_packages) != 1:
        raise ValueError(
            "expected exactly one package entry named "
            f"'time-messenger-home-assistant', found {len(matching_packages)}"
        )
    return matching_packages[0]["version"]


def changelog_version(path: Path) -> object:
    changelog = path.read_text(encoding="utf-8")
    match = re.search(r"^## \[?([^\]\s]+)\]?", changelog, re.MULTILINE)
    if match is None:
        raise KeyError("no release heading")
    return match.group(1)


def requested_tag(explicit_tag: str | None) -> str | None:
    """Return the explicit tag, or GitHub's tag only in a tag-ref context."""
    if explicit_tag is not None:
        return explicit_tag
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        return os.environ.get("GITHUB_REF_NAME")
    return None


def check(root: Path, tag: str | None) -> None:
    """Check parity without mutating the repository."""
    versions = {
        "manifest.json": load_version(
            root / "custom_components/time_messenger/manifest.json",
            "manifest.json",
            manifest_version,
        ),
        "pyproject.toml": load_version(root / "pyproject.toml", "pyproject.toml", project_version),
        "uv.lock project entry": load_version(
            root / "uv.lock", "uv.lock project entry", lock_version
        ),
        "CHANGELOG.md heading": load_version(
            root / "CHANGELOG.md", "CHANGELOG.md heading", changelog_version
        ),
    }
    expected = versions["manifest.json"]
    drifted = {surface: version for surface, version in versions.items() if version != expected}
    if drifted:
        found = ", ".join(f"{surface}={version}" for surface, version in drifted.items())
        fail(f"version drift from manifest.json={expected}: {found}")

    if tag is not None:
        expected_tag = f"v{expected}"
        if tag != expected_tag:
            fail(f"tag={tag!r}; expected {expected_tag!r}")

    print(f"release version parity passed: {expected}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: current directory)",
    )
    parser.add_argument("--tag", help="release tag to validate; overrides GitHub tag environment")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    check(args.root.resolve(), requested_tag(args.tag))


if __name__ == "__main__":
    main()
