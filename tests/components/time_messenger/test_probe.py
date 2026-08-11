"""Tests for the manual tenant probe input boundary."""

import sys

import pytest

from scripts import probe_time_tenant


@pytest.mark.parametrize("duration", ["0", "-1", "nan", "inf"])
def test_probe_rejects_nonpositive_or_nonfinite_duration(
    monkeypatch: pytest.MonkeyPatch, duration: str
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe_time_tenant.py",
            "--origin",
            "https://time.example",
            "--auth-mode",
            "pat",
            "--duration",
            duration,
        ],
    )
    with pytest.raises(SystemExit):
        probe_time_tenant.arguments()


def test_probe_rejects_origin_outside_production_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe_time_tenant.py",
            "--origin",
            "http://time.example",
            "--auth-mode",
            "pat",
        ],
    )
    with pytest.raises(SystemExit):
        probe_time_tenant.arguments()
