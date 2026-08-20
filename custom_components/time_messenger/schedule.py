"""Pure weekly wall-clock schedule for the optional online keeper.

For intervals that cross midnight, a selected weekday always identifies the
day on which the interval starts. Boundaries are start-inclusive and
end-exclusive. Callers supply an aware datetime in Home Assistant's local
timezone; this module performs no timezone discovery of its own.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo

WEEKDAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_WEEKDAY_INDEX = {name: index for index, name in enumerate(WEEKDAYS)}
_CLOCK_PATTERN = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")


def parse_weekdays(values: Iterable[str]) -> frozenset[str]:
    """Validate and freeze canonical weekday names."""

    if isinstance(values, (str, bytes)):
        raise ValueError("weekdays must be a collection of weekday names")
    try:
        weekdays = tuple(values)
    except TypeError as err:
        raise ValueError("weekdays must be a collection of weekday names") from err
    if not weekdays:
        raise ValueError("at least one weekday is required")
    if any(not isinstance(value, str) or value not in _WEEKDAY_INDEX for value in weekdays):
        raise ValueError("weekdays must use mon, tue, wed, thu, fri, sat, or sun")
    return frozenset(weekdays)


def parse_clock(value: str) -> time:
    """Parse the exact HH:MM:SS representation used by integration options."""

    if not isinstance(value, str) or (match := _CLOCK_PATTERN.fullmatch(value)) is None:
        raise ValueError("time must use HH:MM:SS")
    hour, minute, second = (int(part) for part in match.groups())
    try:
        return time(hour, minute, second)
    except ValueError as err:
        raise ValueError("time must use a valid 24-hour HH:MM:SS value") from err


@dataclass(frozen=True, slots=True, init=False)
class KeepOnlineSchedule:
    """Immutable weekly schedule with local wall-clock boundaries."""

    weekdays: frozenset[str]
    start: time
    end: time
    _weekday_indexes: frozenset[int] = field(repr=False, compare=False)

    def __init__(self, weekdays: Iterable[str], start: str, end: str) -> None:
        parsed_weekdays = parse_weekdays(weekdays)
        parsed_start = parse_clock(start)
        parsed_end = parse_clock(end)
        if parsed_start == parsed_end:
            raise ValueError("schedule start and end must differ")
        object.__setattr__(self, "weekdays", parsed_weekdays)
        object.__setattr__(self, "start", parsed_start)
        object.__setattr__(self, "end", parsed_end)
        object.__setattr__(
            self,
            "_weekday_indexes",
            frozenset(_WEEKDAY_INDEX[value] for value in parsed_weekdays),
        )

    def is_active(self, now: datetime) -> bool:
        """Return whether ``now`` belongs to any selected weekly interval."""

        return self._active_end(now) is not None

    def seconds_until_end(self, now: datetime) -> float | None:
        """Return positive elapsed seconds to the active interval's end."""

        end = self._active_end(now)
        if end is None:
            return None
        delay = _future_delay(now, end)
        if delay is None:
            raise RuntimeError("active schedule end did not resolve to a future instant")
        return delay

    def seconds_until_next_start(self, now: datetime) -> float:
        """Return positive elapsed seconds to the next strictly future start."""

        zone = _require_aware(now)
        for days_ahead in range(8):
            start_day = now.date() + timedelta(days=days_ahead)
            if start_day.weekday() not in self._weekday_indexes:
                continue
            candidate = _local_boundary(start_day, self.start, zone, prefer_late=False)
            if (delay := _future_delay(now, candidate)) is not None:
                return delay
        raise RuntimeError("weekly schedule has no future start")

    def _active_end(self, now: datetime) -> datetime | None:
        zone = _require_aware(now)
        now_utc = now.astimezone(UTC)
        active_ends: list[datetime] = []
        for days_ago in (1, 0):
            start_day = now.date() - timedelta(days=days_ago)
            if start_day.weekday() not in self._weekday_indexes:
                continue
            start = _local_boundary(start_day, self.start, zone, prefer_late=False)
            end_day = start_day + timedelta(days=self.start > self.end)
            end = _local_boundary(end_day, self.end, zone, prefer_late=True)
            if start.astimezone(UTC) <= now_utc < end.astimezone(UTC):
                active_ends.append(end)
        if not active_ends:
            return None
        return max(active_ends, key=lambda value: value.astimezone(UTC))


def _require_aware(value: datetime) -> tzinfo:
    zone = value.tzinfo
    if zone is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return zone


def _future_delay(now: datetime, future: datetime) -> float | None:
    delay = (future.astimezone(UTC) - now.astimezone(UTC)).total_seconds()
    return delay if math.isfinite(delay) and delay > 0 else None


def _local_boundary(
    day: date,
    clock: time,
    zone: tzinfo,
    *,
    prefer_late: bool,
) -> datetime:
    """Resolve a local boundary, including ambiguous or missing wall times.

    For a repeated time, starts use the first occurrence and ends the last so
    an interval remains continuous. A missing wall time is normalized forward
    by the UTC-offset gap, preserving its minute and second (02:30 -> 03:30 for
    a one-hour spring transition).
    """

    naive = datetime.combine(day, clock)
    raw_candidates = [naive.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    valid: list[datetime] = []
    normalized: list[datetime] = []
    for candidate in raw_candidates:
        round_trip = candidate.astimezone(UTC).astimezone(zone)
        normalized.append(round_trip)
        if round_trip.replace(tzinfo=None) == naive and round_trip.fold == candidate.fold:
            valid.append(candidate)

    if valid:
        unique = {candidate.astimezone(UTC): candidate for candidate in valid}
        ordered = sorted(unique.values(), key=lambda value: value.astimezone(UTC))
        return ordered[-1] if prefer_late else ordered[0]

    after_gap = [value for value in normalized if value.replace(tzinfo=None) > naive]
    if after_gap:
        return min(
            after_gap,
            key=lambda value: (value.replace(tzinfo=None), value.astimezone(UTC)),
        )
    return max(normalized, key=lambda value: value.astimezone(UTC))
