from __future__ import annotations

from datetime import date, timedelta

OPERATION_PERIOD_LABELS: dict[str, str] = {
    "post_shopping_discount": "우체국쇼핑할인",
    "special_communication": "특별소통기간",
    "no_parcel_day": "위탁배달원 하계 휴식기간",
}

SPECIAL_COMMUNICATION_PERIOD_TYPES = frozenset({"special_communication", "post_shopping_discount"})
SPECIAL_PERIOD_BLEND_WEIGHT = 0.5


def is_date_in_operation_period(check_date: date, period: dict) -> bool:
    start = date.fromisoformat(period["startDate"])
    end = date.fromisoformat(period["endDate"])
    return start <= check_date <= end


def get_operation_periods_for_date(check_date: date, periods: list[dict]) -> list[dict]:
    return [period for period in periods if is_date_in_operation_period(check_date, period)]


def operation_period_labels(periods: list[dict]) -> list[str]:
    return [OPERATION_PERIOD_LABELS.get(period["periodType"], period["periodType"]) for period in periods]


def classify_forecast_period_category(target_day: date, periods: list[dict]) -> str:
    active = get_operation_periods_for_date(target_day, periods)
    if any(period["periodType"] == "no_parcel_day" for period in active):
        return "no_parcel"
    if any(period["periodType"] in SPECIAL_COMMUNICATION_PERIOD_TYPES for period in active):
        return "special"
    return "normal"


def _period_day_index(target_day: date, period: dict) -> tuple[int, int]:
    start = date.fromisoformat(period["startDate"])
    end = date.fromisoformat(period["endDate"])
    index = (target_day - start).days
    length = (end - start).days + 1
    return index, length


def _no_parcel_blend_weight(day_index: int, period_length: int) -> float:
    if period_length <= 1:
        return 0.5
    distance_from_edges = min(day_index, period_length - 1 - day_index)
    max_distance = max(period_length // 2, 1)
    return min(1.0, (distance_from_edges / max_distance) * 0.8 + 0.1)


def _blend_volume(base: float, reference: float, reference_weight: float) -> float:
    weight = max(0.0, min(1.0, reference_weight))
    return round(max(base * (1.0 - weight) + reference * weight, 0.0), 1)


def compute_historical_no_parcel_avg(
    periods: list[dict],
    volume_by_date: dict[str, float],
    before_date: date,
) -> float | None:
    values: list[float] = []
    for period in periods:
        if period["periodType"] != "no_parcel_day":
            continue
        start = date.fromisoformat(period["startDate"])
        end = date.fromisoformat(period["endDate"])
        current = start
        while current <= end:
            if current < before_date:
                volume = volume_by_date.get(current.isoformat())
                if volume is not None:
                    values.append(volume)
            current += timedelta(days=1)
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def compute_historical_same_weekday_in_period(
    period_type: str,
    target_day: date,
    periods: list[dict],
    volume_by_date: dict[str, float],
    before_date: date,
) -> float | None:
    weekday = target_day.weekday()
    values: list[float] = []
    for period in periods:
        if period["periodType"] != period_type:
            continue
        end = date.fromisoformat(period["endDate"])
        if end >= before_date:
            continue
        start = date.fromisoformat(period["startDate"])
        current = start
        while current <= end:
            if current.weekday() == weekday and current < before_date:
                volume = volume_by_date.get(current.isoformat())
                if volume is not None:
                    values.append(volume)
            current += timedelta(days=1)
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def compute_historical_special_period_avg(
    target_day: date,
    periods: list[dict],
    volume_by_date: dict[str, float],
    before_date: date,
    *,
    period_types: frozenset[str] = SPECIAL_COMMUNICATION_PERIOD_TYPES,
) -> float | None:
    weekday = target_day.weekday()
    values: list[float] = []
    for period in periods:
        if period["periodType"] not in period_types:
            continue
        end = date.fromisoformat(period["endDate"])
        if end >= before_date:
            continue
        start = date.fromisoformat(period["startDate"])
        current = start
        while current <= end:
            if current.weekday() == weekday and current < before_date:
                volume = volume_by_date.get(current.isoformat())
                if volume is not None and volume > 0:
                    values.append(volume)
            current += timedelta(days=1)
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _no_parcel_reference(
    target_day: date,
    periods: list[dict],
    volume_by_date: dict[str, float] | None,
    before_date: date,
    historical_no_parcel_avg: float | None,
) -> float | None:
    if volume_by_date:
        same_weekday = compute_historical_same_weekday_in_period(
            "no_parcel_day",
            target_day,
            periods,
            volume_by_date,
            before_date,
        )
        if same_weekday is not None:
            return same_weekday
    return historical_no_parcel_avg


def no_parcel_period_features(
    target_day: date,
    operation_periods: list[dict] | None,
) -> tuple[float, float]:
    if not operation_periods:
        return 0.0, 0.0
    active = get_operation_periods_for_date(target_day, operation_periods)
    no_parcel = [period for period in active if period["periodType"] == "no_parcel_day"]
    if not no_parcel:
        return 0.0, 0.0
    day_index, period_length = _period_day_index(target_day, no_parcel[0])
    denominator = max(period_length - 1, 1)
    return day_index / denominator, (period_length - day_index - 1) / denominator


def apply_operation_period_volume_adjustment(
    volume: float,
    target_day: date,
    periods: list[dict],
    *,
    historical_no_parcel_avg: float | None = None,
    volume_by_date: dict[str, float] | None = None,
    before_date: date | None = None,
) -> tuple[float, tuple[str, ...]]:
    active = get_operation_periods_for_date(target_day, periods)
    labels = tuple(operation_period_labels(active))
    if not active:
        return volume, labels

    adjusted = volume
    cutoff = before_date or target_day
    no_parcel_periods = [period for period in active if period["periodType"] == "no_parcel_day"]

    if no_parcel_periods:
        period = no_parcel_periods[0]
        day_index, period_length = _period_day_index(target_day, period)
        ref_weight = _no_parcel_blend_weight(day_index, period_length)
        reference = _no_parcel_reference(
            target_day,
            periods,
            volume_by_date,
            cutoff,
            historical_no_parcel_avg,
        )
        if reference is not None:
            adjusted = _blend_volume(volume, reference, ref_weight)
        else:
            adjusted = _blend_volume(volume, max(volume * 0.05, 0.0), ref_weight)
    else:
        special_active = [
            period
            for period in active
            if period["periodType"] in SPECIAL_COMMUNICATION_PERIOD_TYPES
        ]
        if special_active and volume_by_date:
            reference = compute_historical_special_period_avg(
                target_day,
                periods,
                volume_by_date,
                cutoff,
            )
            if reference is not None:
                adjusted = _blend_volume(volume, reference, SPECIAL_PERIOD_BLEND_WEIGHT)

    return round(max(adjusted, 0.0), 1), labels
