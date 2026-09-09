from __future__ import annotations

import re

_ARRIVAL_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def quota_overage(actual: int | None, standard: int | None) -> int | None:
    if actual is None or standard is None:
        return None
    return max(actual - standard, 0)


def quota_status(actual: int | None, standard: int | None) -> str:
    overage = quota_overage(actual, standard)
    if overage is None:
        return "UNKNOWN"
    return "WARNING" if overage > 0 else "NORMAL"


def is_arrival_after_23(
    arrival_time: str | None,
    *,
    volume: int | None = None,
    vehicles_actual: int | None = None,
) -> bool:
    """최종도착이 23:00을 넘으면 True. 익일 00~06시도 포함한다."""
    if not arrival_time:
        return False
    match = _ARRIVAL_TIME_RE.fullmatch(arrival_time.strip())
    if not match:
        return False
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return False
    if hour == 23:
        return minute > 0
    if 0 <= hour <= 6:
        dummy_midnight = hour == 0 and minute == 0 and not (volume or 0) and not (vehicles_actual or 0)
        return not dummy_midnight
    return False


def office_status_label(*, overage: bool, delayed: bool) -> str:
    if overage and delayed:
        return "초과/지연"
    if overage:
        return "초과"
    if delayed:
        return "지연"
    return "정상"


def office_count_volume_text(label: str, count: int, volume: int) -> str:
    return f"{label} {count}곳(물량 {volume:,}개)"
