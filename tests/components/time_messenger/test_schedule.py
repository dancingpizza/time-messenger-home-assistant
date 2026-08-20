"""Tests for the pure online-keeper weekly schedule."""

import math
from dataclasses import FrozenInstanceError
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from custom_components.time_messenger.schedule import KeepOnlineSchedule, parse_clock

MOSCOW = ZoneInfo("Europe/Moscow")


def local(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """Return a date in the Monday-to-Sunday week starting 2026-08-17."""

    return datetime(2026, 8, day, hour, minute, second, tzinfo=MOSCOW)


@pytest.mark.parametrize(
    "weekdays",
    [[], "mon", ["monday"], ["MON"], ["mon", 1]],
)
def test_invalid_weekdays_are_rejected(weekdays: object) -> None:
    with pytest.raises(ValueError):
        KeepOnlineSchedule(weekdays, "09:00:00", "18:00:00")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    ["", "9:00:00", "09:00", "24:00:00", "23:60:00", "23:00:60", "09:00:00.1"],
)
def test_clock_requires_exact_valid_hh_mm_ss(value: str) -> None:
    with pytest.raises(ValueError):
        parse_clock(value)


def test_equal_start_and_end_are_rejected() -> None:
    with pytest.raises(ValueError, match="must differ"):
        KeepOnlineSchedule(["mon"], "09:00:00", "09:00:00")


def test_schedule_is_immutable_and_canonicalizes_duplicate_days() -> None:
    schedule = KeepOnlineSchedule(["fri", "mon", "fri"], "09:00:00", "18:00:00")

    assert schedule.weekdays == frozenset({"mon", "fri"})
    assert schedule.start == time(9)
    assert schedule.end == time(18)
    with pytest.raises(FrozenInstanceError):
        schedule.start = time(10)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("now", "active"),
    [
        (local(17, 8, 59, 59), False),
        (local(17, 9), True),
        (local(17, 17, 59, 59), True),
        (local(17, 18), False),
        (local(21, 17, 59, 59), True),
        (local(21, 18), False),
        (local(22, 12), False),
        (local(23, 12), False),
    ],
)
def test_mon_fri_activity_and_exact_boundaries(now: datetime, active: bool) -> None:
    schedule = KeepOnlineSchedule(["mon", "tue", "wed", "thu", "fri"], "09:00:00", "18:00:00")

    assert schedule.is_active(now) is active


def test_seconds_until_end_is_positive_only_while_active() -> None:
    schedule = KeepOnlineSchedule(["mon"], "09:00:00", "18:00:00")

    assert schedule.seconds_until_end(local(17, 9)) == 9 * 60 * 60
    assert schedule.seconds_until_end(local(17, 17, 59, 59)) == 1
    assert schedule.seconds_until_end(local(17, 18)) is None


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (local(17, 8), 60 * 60),
        (local(17, 9), 24 * 60 * 60),
        (local(21, 18), 63 * 60 * 60),
        (local(22, 12), 45 * 60 * 60),
    ],
)
def test_seconds_until_next_mon_fri_start(now: datetime, expected: float) -> None:
    schedule = KeepOnlineSchedule(["mon", "tue", "wed", "thu", "fri"], "09:00:00", "18:00:00")

    assert schedule.seconds_until_next_start(now) == expected


def test_weekend_schedule_is_independent_from_weekdays() -> None:
    schedule = KeepOnlineSchedule(["sat", "sun"], "10:00:00", "11:00:00")

    assert schedule.is_active(local(21, 10, 30)) is False
    assert schedule.is_active(local(22, 10, 30)) is True
    assert schedule.is_active(local(23, 10, 30)) is True
    assert schedule.is_active(local(24, 10, 30)) is False


def test_cross_midnight_uses_selected_day_as_start_day() -> None:
    friday = KeepOnlineSchedule(["fri"], "22:00:00", "06:00:00")
    thursday = KeepOnlineSchedule(["thu"], "22:00:00", "06:00:00")

    assert friday.is_active(local(21, 21, 59, 59)) is False
    assert friday.is_active(local(21, 22)) is True
    assert friday.seconds_until_end(local(21, 22)) == 8 * 60 * 60
    assert friday.is_active(local(22, 5, 59, 59)) is True
    assert friday.seconds_until_end(local(22, 5, 59, 59)) == 1
    assert friday.is_active(local(22, 6)) is False
    assert friday.is_active(local(21, 1)) is False
    assert thursday.is_active(local(21, 1)) is True


def test_cross_midnight_wraps_sunday_into_monday() -> None:
    schedule = KeepOnlineSchedule(["sun"], "22:00:00", "06:00:00")

    assert schedule.is_active(local(23, 22)) is True
    assert schedule.is_active(local(24, 5, 59, 59)) is True
    assert schedule.is_active(local(24, 6)) is False


def test_next_start_wraps_to_next_week_and_is_strictly_future() -> None:
    schedule = KeepOnlineSchedule(["sun"], "10:00:00", "11:00:00")

    assert schedule.seconds_until_next_start(local(23, 10)) == 7 * 24 * 60 * 60
    assert schedule.seconds_until_next_start(local(24, 12)) == 6 * 24 * 60 * 60 - 2 * 60 * 60


def test_delays_use_elapsed_seconds_across_timezone_offset_change() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    schedule = KeepOnlineSchedule(["sun"], "01:30:00", "04:30:00")
    spring_forward_start = datetime(2026, 3, 29, 1, 30, tzinfo=berlin)

    assert schedule.is_active(spring_forward_start) is True
    assert schedule.seconds_until_end(spring_forward_start) == 2 * 60 * 60
    assert schedule.seconds_until_next_start(spring_forward_start) > 0


def test_nonexistent_boundary_is_shifted_forward_by_dst_gap() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    schedule = KeepOnlineSchedule(["sun"], "02:30:00", "04:00:00")

    assert schedule.is_active(datetime(2026, 3, 29, 3, 29, 59, tzinfo=berlin)) is False
    assert schedule.is_active(datetime(2026, 3, 29, 3, 30, tzinfo=berlin)) is True


def test_ambiguous_boundaries_use_first_start_and_last_end_fold() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    schedule = KeepOnlineSchedule(["sun"], "02:15:00", "02:45:00")
    first_start = datetime(2026, 10, 25, 2, 15, tzinfo=berlin, fold=0)
    second_end = datetime(2026, 10, 25, 2, 45, tzinfo=berlin, fold=1)

    assert schedule.is_active(first_start) is True
    assert schedule.seconds_until_end(first_start) == 90 * 60
    assert schedule.is_active(second_end) is False


@pytest.mark.parametrize("method", ["is_active", "seconds_until_end", "seconds_until_next_start"])
def test_naive_datetime_is_rejected(method: str) -> None:
    schedule = KeepOnlineSchedule(["mon"], "09:00:00", "18:00:00")
    naive = datetime(2026, 8, 17, 9)

    with pytest.raises(ValueError, match="timezone-aware"):
        getattr(schedule, method)(naive)


@pytest.mark.parametrize(
    "now",
    [
        local(17, 9),
        local(17, 18),
        local(22, 12),
        local(23, 23, 59, 59),
    ],
)
def test_next_start_delay_is_always_finite_and_positive(now: datetime) -> None:
    schedule = KeepOnlineSchedule(["mon", "wed", "fri"], "09:00:00", "18:00:00")

    delay = schedule.seconds_until_next_start(now)
    assert math.isfinite(delay)
    assert delay > 0
