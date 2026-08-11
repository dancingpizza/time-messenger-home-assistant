"""Contract tests for the HACS distribution package."""

import json
import re
import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[3]
INTEGRATION_ROOT = REPOSITORY_ROOT / "custom_components" / "time_messenger"
RELEASE_VERSION = "0.0.3"
RELEASE_TAG = f"v{RELEASE_VERSION}"
FORBIDDEN_HACS_KEYS = {
    "content_in_root",
    "country",
    "filename",
    "persistent_directory",
    "zip_release",
}
EXPECTED_MIT_LICENSE = """MIT License

Copyright (c) 2026 dancingpizza

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def load_json(path: Path) -> dict[str, object]:
    """Load a JSON object from the repository."""
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_hacs_uses_the_standard_single_integration_layout() -> None:
    hacs = load_json(REPOSITORY_ROOT / "hacs.json")

    assert hacs == {
        "name": "Time Messenger",
        "render_readme": True,
        "homeassistant": "2026.8.1",
    }
    assert FORBIDDEN_HACS_KEYS.isdisjoint(hacs)

    integration_directories = {
        path.name
        for path in (REPOSITORY_ROOT / "custom_components").iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    }
    assert integration_directories == {"time_messenger"}
    assert INTEGRATION_ROOT.is_dir()
    assert (INTEGRATION_ROOT / "brand" / "icon.png").is_file()


def test_manifest_contains_exact_distribution_and_runtime_metadata() -> None:
    manifest = load_json(INTEGRATION_ROOT / "manifest.json")

    assert manifest == {
        "domain": "time_messenger",
        "name": "Time Messenger",
        "codeowners": ["@dancingpizza"],
        "config_flow": True,
        "dependencies": ["application_credentials"],
        "documentation": "https://github.com/dancingpizza/time-messenger-home-assistant",
        "integration_type": "service",
        "iot_class": "cloud_push",
        "issue_tracker": "https://github.com/dancingpizza/time-messenger-home-assistant/issues",
        "requirements": [],
        "version": RELEASE_VERSION,
    }


def test_release_version_is_identical_on_every_release_surface() -> None:
    manifest_version = load_json(INTEGRATION_ROOT / "manifest.json")["version"]
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as project_file:
        package_version = tomllib.load(project_file)["project"]["version"]
    with (REPOSITORY_ROOT / "uv.lock").open("rb") as lock_file:
        locked_packages = tomllib.load(lock_file)["package"]
    locked_package_version = next(
        package["version"]
        for package in locked_packages
        if package["name"] == "time-messenger-home-assistant"
    )
    changelog = (REPOSITORY_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog_versions = re.findall(r"^## \[?(\d+\.\d+\.\d+)\]?", changelog, re.MULTILINE)

    assert manifest_version == package_version == locked_package_version == RELEASE_VERSION
    assert RELEASE_VERSION in changelog_versions
    assert RELEASE_TAG == "v0.0.3"


def test_repository_contains_full_mit_license() -> None:
    license_text = (REPOSITORY_ROOT / "LICENSE").read_text(encoding="utf-8")

    assert license_text == EXPECTED_MIT_LICENSE
