from __future__ import annotations

from datetime import date, timedelta

OPERATION_PERIOD_LABELS: dict[str, str] = {
    "post_shopping_discount": "우체국쇼핑대전",
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
    include_no_parcel: bool = True,
) -> tuple[float, tuple[str, ...]]:
    active = get_operation_periods_for_date(target_day, periods)
    labeled = (
        [period for period in active if period["periodType"] != "no_parcel_day"]
        if not include_no_parcel
        else active
    )
    labels = tuple(operation_period_labels(labeled))
    if not active:
        return volume, labels

    adjusted = volume
    cutoff = before_date or target_day
    no_parcel_periods = [
        period
        for period in active
        if include_no_parcel and period["periodType"] == "no_parcel_day"
    ]

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


SPECIAL_PERIOD_ANALYSIS_TYPE = "special_communication"
SPECIAL_PERIOD_WINDOW_PAD_DAYS = 7
SPECIAL_PERIOD_PRIOR_MISSING_MESSAGE = "전년 특별소통기간이 등록되지 않았습니다"
SPECIAL_PERIOD_NONE_REGISTERED_MESSAGE = "등록된 특별소통기간이 없습니다."
_MACHINE_STREAMS = ("dispatch", "arrival")
_MACHINE_DECKS = (1, 2, 3)


def period_length_days(period: dict) -> int:
    start = date.fromisoformat(period["startDate"])
    end = date.fromisoformat(period["endDate"])
    return (end - start).days + 1


def expand_period_window(
    period: dict,
    pad_days: int = SPECIAL_PERIOD_WINDOW_PAD_DAYS,
) -> tuple[date, date]:
    start = date.fromisoformat(period["startDate"])
    end = date.fromisoformat(period["endDate"])
    return start - timedelta(days=pad_days), end + timedelta(days=pad_days)


def subtract_one_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return date(day.year - 1, 2, 28)


def match_prior_year_period(
    current: dict,
    periods: list[dict],
    *,
    period_type: str = SPECIAL_PERIOD_ANALYSIS_TYPE,
) -> dict | None:
    current_start = date.fromisoformat(current["startDate"])
    target = subtract_one_year(current_start)
    current_id = current.get("id")
    candidates: list[tuple[int, date, dict]] = []
    for period in periods:
        if period.get("periodType") != period_type:
            continue
        if current_id is not None and period.get("id") == current_id:
            continue
        start = date.fromisoformat(period["startDate"])
        if start >= current_start:
            continue
        delta = abs((start - target).days)
        candidates.append((delta, start, period))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def select_special_period(
    periods: list[dict],
    *,
    period_id: int | None = None,
    reference_date: date | None = None,
    period_type: str = SPECIAL_PERIOD_ANALYSIS_TYPE,
) -> dict | None:
    special = [period for period in periods if period.get("periodType") == period_type]
    if period_id is not None:
        for period in special:
            if period.get("id") == period_id:
                return period
        return None
    if not special:
        return None
    if reference_date is not None:
        covering = [period for period in special if is_date_in_operation_period(reference_date, period)]
        if covering:
            covering.sort(key=lambda period: (period["startDate"], period.get("id") or 0), reverse=True)
            return covering[0]
    special.sort(key=lambda period: (period["startDate"], period.get("id") or 0), reverse=True)
    return special[0]


def comparison_offsets(
    current_length: int,
    prior_length: int | None,
    pad_days: int = SPECIAL_PERIOD_WINDOW_PAD_DAYS,
) -> list[int]:
    max_length = current_length if prior_length is None else max(current_length, prior_length)
    return list(range(-pad_days, max_length + pad_days))


def offset_label(offset: int) -> str:
    if offset == 0:
        return "D+0"
    if offset > 0:
        return f"D+{offset}"
    return f"D{offset}"


def is_offset_in_window(
    offset: int,
    length: int,
    pad_days: int = SPECIAL_PERIOD_WINDOW_PAD_DAYS,
) -> bool:
    return -pad_days <= offset <= (length - 1) + pad_days


def is_offset_in_period(offset: int, length: int) -> bool:
    return 0 <= offset < length


def quota_compliance_rate(actual: int | float | None, standard: int | float | None) -> float | None:
    if actual is None or standard in (None, 0):
        return None
    return round((actual / standard) * 100, 1)


def yoy_change_percent(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return round((current - prior) / prior * 100, 1)


def _sum_skip_none(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    total = sum(present)
    if all(float(value).is_integer() for value in present):
        return int(total)
    return round(float(total), 1)


def _mean_skip_none(values: list[float | None], digits: int = 1) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), digits)


def _kpi_pair(current: float | None, prior: float | None) -> dict:
    return {
        "current": current,
        "prior": prior,
        "changePercent": yoy_change_percent(current, prior),
    }


def _period_public(period: dict) -> dict:
    window_start, window_end = expand_period_window(period)
    return {
        "id": period.get("id"),
        "periodType": period.get("periodType"),
        "startDate": period["startDate"],
        "endDate": period["endDate"],
        "note": period.get("note"),
        "lengthDays": period_length_days(period),
        "windowStart": window_start.isoformat(),
        "windowEnd": window_end.isoformat(),
    }


def _lookup_day(
    daily_by_date: dict[str, dict],
    period_start: date | None,
    offset: int,
    length: int | None,
) -> dict | None:
    if period_start is None or length is None:
        return None
    if not is_offset_in_window(offset, length):
        return None
    return daily_by_date.get((period_start + timedelta(days=offset)).isoformat())


def _metric_at(day: dict | None, key: str) -> float | None:
    if not day:
        return None
    value = day.get(key)
    return value if value is not None else None


def _machine_at(day: dict | None, stream: str, deck: int, field: str) -> float | None:
    if not day:
        return None
    item = ((day.get("machineSorting") or {}).get(stream) or {}).get(deck) or {}
    value = item.get(field)
    return value if value is not None else None


def _empty_machine_stream() -> dict:
    payload: dict[str, float | None] = {}
    for deck in _MACHINE_DECKS:
        payload[f"deck{deck}VolumeCurrent"] = None
        payload[f"deck{deck}VolumePrior"] = None
        payload[f"deck{deck}ShareCurrent"] = None
        payload[f"deck{deck}SharePrior"] = None
    return payload


def build_special_period_analysis(
    periods: list[dict],
    daily_by_date: dict[str, dict],
    *,
    period_id: int | None = None,
    reference_date: date | None = None,
) -> dict:
    special = [period for period in periods if period.get("periodType") == SPECIAL_PERIOD_ANALYSIS_TYPE]
    available = [
        {
            "id": period.get("id"),
            "periodType": period.get("periodType"),
            "startDate": period["startDate"],
            "endDate": period["endDate"],
            "note": period.get("note"),
        }
        for period in sorted(special, key=lambda item: (item["startDate"], item.get("id") or 0), reverse=True)
    ]

    if period_id is not None:
        current = next((period for period in special if period.get("id") == period_id), None)
        if current is None:
            return {
                "availablePeriods": available,
                "sameYearPeriods": [],
                "currentPeriod": None,
                "priorPeriod": None,
                "priorMissing": True,
                "message": None,
                "notFound": True,
                "series": [],
                "kpi": None,
            }
    else:
        current = select_special_period(periods, reference_date=reference_date)

    if current is None:
        return {
            "availablePeriods": available,
            "sameYearPeriods": [],
            "currentPeriod": None,
            "priorPeriod": None,
            "priorMissing": True,
            "message": SPECIAL_PERIOD_NONE_REGISTERED_MESSAGE,
            "series": [],
            "kpi": None,
        }

    prior = match_prior_year_period(current, periods)
    current_start = date.fromisoformat(current["startDate"])
    prior_start = date.fromisoformat(prior["startDate"]) if prior else None
    current_length = period_length_days(current)
    prior_length = period_length_days(prior) if prior else None
    offsets = comparison_offsets(current_length, prior_length)
    current_year = current_start.year
    same_year_periods = [
        item
        for item in available
        if date.fromisoformat(item["startDate"]).year == current_year
    ]

    series: list[dict] = []
    volume_total_current: list[float | None] = []
    volume_total_prior: list[float | None] = []
    volume_dispatch_current: list[float | None] = []
    volume_dispatch_prior: list[float | None] = []
    volume_arrival_current: list[float | None] = []
    volume_arrival_prior: list[float | None] = []
    quota_actual_current: list[float | None] = []
    quota_actual_prior: list[float | None] = []
    quota_standard_current: list[float | None] = []
    quota_standard_prior: list[float | None] = []
    quota_compliance_current: list[float | None] = []
    quota_compliance_prior: list[float | None] = []
    machine_share_current: dict[str, dict[int, list[float | None]]] = {
        stream: {deck: [] for deck in _MACHINE_DECKS} for stream in _MACHINE_STREAMS
    }
    machine_share_prior: dict[str, dict[int, list[float | None]]] = {
        stream: {deck: [] for deck in _MACHINE_DECKS} for stream in _MACHINE_STREAMS
    }

    for offset in offsets:
        current_day = _lookup_day(daily_by_date, current_start, offset, current_length)
        prior_day = _lookup_day(daily_by_date, prior_start, offset, prior_length)
        current_in_window = is_offset_in_window(offset, current_length)
        prior_in_window = prior_length is not None and is_offset_in_window(offset, prior_length)
        machine_sorting = {}
        for stream in _MACHINE_STREAMS:
            stream_payload = _empty_machine_stream()
            for deck in _MACHINE_DECKS:
                current_volume = _machine_at(current_day, stream, deck, "volume")
                prior_volume = _machine_at(prior_day, stream, deck, "volume")
                current_share = _machine_at(current_day, stream, deck, "share")
                prior_share = _machine_at(prior_day, stream, deck, "share")
                stream_payload[f"deck{deck}VolumeCurrent"] = current_volume
                stream_payload[f"deck{deck}VolumePrior"] = prior_volume
                stream_payload[f"deck{deck}ShareCurrent"] = current_share
                stream_payload[f"deck{deck}SharePrior"] = prior_share
                machine_share_current[stream][deck].append(current_share)
                machine_share_prior[stream][deck].append(prior_share)
            machine_sorting[stream] = stream_payload

        total_current = _metric_at(current_day, "totalVolume")
        total_prior = _metric_at(prior_day, "totalVolume")
        dispatch_current = _metric_at(current_day, "dispatchVolume")
        dispatch_prior = _metric_at(prior_day, "dispatchVolume")
        arrival_current = _metric_at(current_day, "arrivalVolume")
        arrival_prior = _metric_at(prior_day, "arrivalVolume")
        actual_current = _metric_at(current_day, "quotaActual")
        actual_prior = _metric_at(prior_day, "quotaActual")
        standard_current = _metric_at(current_day, "quotaStandard")
        standard_prior = _metric_at(prior_day, "quotaStandard")
        compliance_current = _metric_at(current_day, "quotaCompliance")
        compliance_prior = _metric_at(prior_day, "quotaCompliance")

        volume_total_current.append(total_current)
        volume_total_prior.append(total_prior)
        volume_dispatch_current.append(dispatch_current)
        volume_dispatch_prior.append(dispatch_prior)
        volume_arrival_current.append(arrival_current)
        volume_arrival_prior.append(arrival_prior)
        quota_actual_current.append(actual_current)
        quota_actual_prior.append(actual_prior)
        quota_standard_current.append(standard_current)
        quota_standard_prior.append(standard_prior)
        quota_compliance_current.append(compliance_current)
        quota_compliance_prior.append(compliance_prior)

        series.append(
            {
                "offset": offset,
                "label": offset_label(offset),
                "currentDate": (current_start + timedelta(days=offset)).isoformat() if current_in_window else None,
                "priorDate": (prior_start + timedelta(days=offset)).isoformat()
                if prior_start is not None and prior_in_window
                else None,
                "currentInPeriod": is_offset_in_period(offset, current_length),
                "priorInPeriod": prior_length is not None and is_offset_in_period(offset, prior_length),
                "volume": {
                    "totalCurrent": total_current,
                    "totalPrior": total_prior,
                    "dispatchCurrent": dispatch_current,
                    "dispatchPrior": dispatch_prior,
                    "arrivalCurrent": arrival_current,
                    "arrivalPrior": arrival_prior,
                },
                "quota": {
                    "actualCurrent": actual_current,
                    "actualPrior": actual_prior,
                    "standardCurrent": standard_current,
                    "standardPrior": standard_prior,
                    "complianceCurrent": compliance_current,
                    "compliancePrior": compliance_prior,
                },
                "machineSorting": machine_sorting,
            }
        )

    kpi = {
        "totalVolume": _kpi_pair(_sum_skip_none(volume_total_current), _sum_skip_none(volume_total_prior)),
        "dispatchVolume": _kpi_pair(_sum_skip_none(volume_dispatch_current), _sum_skip_none(volume_dispatch_prior)),
        "arrivalVolume": _kpi_pair(_sum_skip_none(volume_arrival_current), _sum_skip_none(volume_arrival_prior)),
        "quotaActual": _kpi_pair(_sum_skip_none(quota_actual_current), _sum_skip_none(quota_actual_prior)),
        "quotaStandard": _kpi_pair(_sum_skip_none(quota_standard_current), _sum_skip_none(quota_standard_prior)),
        "quotaComplianceRate": _kpi_pair(
            _mean_skip_none(quota_compliance_current),
            _mean_skip_none(quota_compliance_prior),
        ),
        "machineShare": {
            stream: {
                f"deck{deck}": _kpi_pair(
                    _mean_skip_none(machine_share_current[stream][deck]),
                    _mean_skip_none(machine_share_prior[stream][deck]),
                )
                for deck in _MACHINE_DECKS
            }
            for stream in _MACHINE_STREAMS
        },
    }

    return {
        "availablePeriods": available,
        "sameYearPeriods": same_year_periods,
        "currentPeriod": _period_public(current),
        "priorPeriod": _period_public(prior) if prior else None,
        "priorMissing": prior is None,
        "message": SPECIAL_PERIOD_PRIOR_MISSING_MESSAGE if prior is None else None,
        "series": series,
        "kpi": kpi,
    }
