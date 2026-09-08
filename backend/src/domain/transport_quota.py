from __future__ import annotations


def quota_overage(actual: int | None, standard: int | None) -> int | None:
    if actual is None or standard is None:
        return None
    return max(actual - standard, 0)


def quota_status(actual: int | None, standard: int | None) -> str:
    overage = quota_overage(actual, standard)
    if overage is None:
        return "UNKNOWN"
    return "WARNING" if overage > 0 else "NORMAL"
