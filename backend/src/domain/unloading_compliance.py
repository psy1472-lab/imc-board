from __future__ import annotations

from dataclasses import dataclass

from domain.hour_slots import HOUR_SLOTS, hour_slot_order, normalize_hour_slot

UNLOADING_COMPLIANCE_RULES = (
    ("collection_vehicles", "수집차량", "22"),
    ("quota_vehicles", "쿼터차량", "23"),
    ("exchange_vehicles", "교환차량", "02"),
)


@dataclass(frozen=True)
class UnloadingCompliance:
    column: str
    label: str
    deadline_slot: str
    total: int
    delayed: int
    rate: float
    severity: str
    message: str


def delayed_hour_slots(deadline_slot: str) -> list[str]:
    deadline = normalize_hour_slot(deadline_slot)
    cutoff = hour_slot_order(deadline)
    return [slot for slot in HOUR_SLOTS if hour_slot_order(slot) > cutoff]


def _row_slot(row) -> str:
    if isinstance(row, dict):
        slot = row.get("hour_slot") or row.get("slot")
    else:
        slot = getattr(row, "hour_slot", None)
        if slot is None:
            slot = row["hour_slot"]
    return normalize_hour_slot(str(slot))


def _row_count(row, column: str) -> int:
    value = None
    if isinstance(row, dict):
        value = row.get(column)
        if value is None:
            value = row.get(column.removesuffix("_vehicles"))
    else:
        value = getattr(row, column, None)
        if value is None:
            try:
                value = row[column]
            except (KeyError, IndexError, TypeError):
                value = None
    return int(value or 0)


def compute_unloading_compliance(rows) -> list[UnloadingCompliance]:
    items: list[UnloadingCompliance] = []
    if not rows:
        return items
    by_slot = {_row_slot(row): row for row in rows}
    for column, label, deadline_slot in UNLOADING_COMPLIANCE_RULES:
        total = sum(_row_count(row, column) for row in rows)
        if total <= 0:
            continue
        delayed = sum(_row_count(by_slot[slot], column) for slot in delayed_hour_slots(deadline_slot) if slot in by_slot)
        on_time = total - delayed
        rate = round((on_time / total) * 100, 1)
        severity = "WARNING" if delayed > 0 else "NORMAL"
        deadline_label = f"{normalize_hour_slot(deadline_slot)}시 기준"
        message = f"{label} 도착시간 준수율 {rate}% (지연 {delayed}/{total}대, {deadline_label})"
        items.append(
            UnloadingCompliance(
                column=column,
                label=label,
                deadline_slot=normalize_hour_slot(deadline_slot),
                total=total,
                delayed=delayed,
                rate=rate,
                severity=severity,
                message=message,
            )
        )
    return items


def unloading_compliance_messages(rows) -> list[dict]:
    return [
        {
            "severity": item.severity,
            "category": "transport",
            "categoryLabel": "운송",
            "message": item.message,
            "source": "rule",
        }
        for item in compute_unloading_compliance(rows)
    ]
