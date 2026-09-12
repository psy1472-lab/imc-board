from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from domain.day_type import is_post_holiday, resolve_day_type
from domain.operation_period import apply_operation_period_volume_adjustment

WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]

DAY_TYPE_LABELS = {
    "weekday": "평일",
    "saturday": "토요일",
    "sunday": "일요일",
    "holiday": "공휴일",
}

# Seasonal Naive(m=7) + 동일 요일 4주 평균 앙상블 (Hyndman 벤치마크 기반)
WEEKDAY_SEASONAL_LATEST_WEIGHT = 0.35
WEEKDAY_SEASONAL_4W_WEIGHT = 0.30
WEEKDAY_SAME_TYPE_BASELINE_WEIGHT = 0.20
WEEKDAY_DRIFT_WEIGHT = 0.15

WEEKEND_SEASONAL_LATEST_WEIGHT = 0.25
WEEKEND_SEASONAL_4W_WEIGHT = 0.35
WEEKEND_SAME_TYPE_BASELINE_WEIGHT = 0.40

# 폴백(동일 요일 데이터 부족 시)
WEEKDAY_WEIGHT_STRONG = 0.45
WEEKDAY_WEIGHT_WEAK = 0.30
RECENT_7D_WEIGHT = 0.25
RECENT_30D_WEIGHT = 0.15
RECENT_3D_WEIGHT = 0.15

TREND_FACTOR_MIN = 0.88
TREND_FACTOR_MAX = 1.12
MOMENTUM_FACTOR_MIN = 0.92
MOMENTUM_FACTOR_MAX = 1.08
DRIFT_DAMPING = 0.5

POST_HOLIDAY_LABEL = "휴일 다음날"
POST_HOLIDAY_FACTOR_MIN = 0.92
POST_HOLIDAY_FACTOR_MAX = 1.18
POST_HOLIDAY_LOOKBACK_WEEKS = 52
POST_HOLIDAY_MIN_SAMPLES = 2
POST_HOLIDAY_BLEND_WEIGHT = 0.35


@dataclass(frozen=True)
class VolumeForecastResult:
    tomorrow_date: str
    tomorrow_weekday_label: str
    tomorrow_day_type: str
    forecast_volume: float
    weekday_average: float | None
    recent_7d_average: float | None
    recent_30d_average: float | None
    recent_3d_average: float | None
    today_volume: float | None
    weekday_sample_count: int
    trend_factor: float
    momentum_factor: float
    recent_trend_direction: str | None
    confidence: str
    forecast_target_note: str | None = None
    seasonal_naive_1w: float | None = None
    seasonal_naive_4w: float | None = None
    forecast_method: str = "seasonal_naive_ensemble"
    operation_period_labels: tuple[str, ...] = ()
    forecast_national_volume: float | None = None


def resolve_forecast_target_date(report_day: date) -> date:
    """IMC 운영 기준 전망 대상일. 금요일 보고서는 토요일을 건너뛰고 일요일을 전망한다."""
    if report_day.weekday() == 4:
        return report_day + timedelta(days=2)
    return report_day + timedelta(days=1)


def forecast_target_note_for(report_day: date, target_day: date) -> str | None:
    if report_day.weekday() == 4 and target_day.weekday() == 6:
        return "토요일 제외, 일요일 기준"
    return None


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _weighted_average(parts: list[tuple[float, float]]) -> float | None:
    if not parts:
        return None
    total_weight = sum(weight for _, weight in parts)
    return sum(value * weight for value, weight in parts) / total_weight


def _recent_trend_direction(recent_volumes: list[float | None]) -> str | None:
    values = [value for value in recent_volumes if value is not None]
    if len(values) < 4:
        return None
    recent_3 = sum(values[-3:]) / 3
    prior = sum(values[:-3]) / len(values[:-3])
    if prior == 0:
        return None
    change_ratio = recent_3 / prior
    if change_ratio >= 1.03:
        return "상승"
    if change_ratio <= 0.97:
        return "하락"
    return "보합"


def _damped_drift_factor(today_volume: float | None, reference: float | None) -> float:
    if today_volume is None or reference in (None, 0):
        return 1.0
    raw = today_volume / reference
    return 1.0 + (raw - 1.0) * DRIFT_DAMPING


def _build_seasonal_ensemble(
    *,
    target_day_type: str,
    seasonal_naive_1w: float | None,
    seasonal_naive_4w: float | None,
    same_type_baseline: float | None,
    weekday_average: float | None,
) -> tuple[float | None, str]:
    baseline = same_type_baseline if same_type_baseline is not None else weekday_average
    is_weekend_target = target_day_type in {"saturday", "sunday", "holiday"}

    if is_weekend_target:
        parts: list[tuple[float, float]] = []
        if seasonal_naive_4w is not None:
            parts.append((seasonal_naive_4w, WEEKEND_SEASONAL_4W_WEIGHT))
        if baseline is not None:
            parts.append((baseline, WEEKEND_SAME_TYPE_BASELINE_WEIGHT))
        if seasonal_naive_1w is not None:
            parts.append((seasonal_naive_1w, WEEKEND_SEASONAL_LATEST_WEIGHT))
        base = _weighted_average(parts)
        if base is not None:
            return base, "seasonal_naive_weekend"
    else:
        parts = []
        if seasonal_naive_1w is not None:
            parts.append((seasonal_naive_1w, WEEKDAY_SEASONAL_LATEST_WEIGHT))
        if seasonal_naive_4w is not None:
            parts.append((seasonal_naive_4w, WEEKDAY_SEASONAL_4W_WEIGHT))
        if baseline is not None:
            parts.append((baseline, WEEKDAY_SAME_TYPE_BASELINE_WEIGHT))
        base = _weighted_average(parts)
        if base is not None:
            return base, "seasonal_naive_weekday"

    return None, "fallback"


def _build_fallback_ensemble(
    *,
    weekday_average: float | None,
    weekday_sample_count: int,
    avg_7d_volume: float | None,
    avg_30d_volume: float | None,
    recent_3d_average: float | None,
) -> float | None:
    parts: list[tuple[float, float]] = []
    if weekday_average is not None:
        weekday_weight = WEEKDAY_WEIGHT_STRONG if weekday_sample_count >= 3 else WEEKDAY_WEIGHT_WEAK
        parts.append((weekday_average, weekday_weight))
    if avg_7d_volume is not None:
        parts.append((avg_7d_volume, RECENT_7D_WEIGHT))
    if avg_30d_volume is not None:
        parts.append((avg_30d_volume, RECENT_30D_WEIGHT))
    if recent_3d_average is not None:
        parts.append((recent_3d_average, RECENT_3D_WEIGHT))
    return _weighted_average(parts)


def estimate_post_holiday_factor(
    target_day: date,
    volume_by_date: dict[str, float] | None,
) -> float | None:
    if not is_post_holiday(target_day) or not volume_by_date:
        return None
    weekday = target_day.weekday()
    post_values: list[float] = []
    normal_values: list[float] = []
    for weeks_back in range(1, POST_HOLIDAY_LOOKBACK_WEEKS + 1):
        candidate = target_day - timedelta(weeks=weeks_back)
        if candidate.weekday() != weekday:
            continue
        value = volume_by_date.get(candidate.isoformat())
        if value is None or value <= 0:
            continue
        if is_post_holiday(candidate):
            post_values.append(value)
        elif resolve_day_type(candidate) == "weekday":
            normal_values.append(value)
    if len(post_values) < POST_HOLIDAY_MIN_SAMPLES or not normal_values:
        return None
    normal_mean = sum(normal_values) / len(normal_values)
    if normal_mean <= 0:
        return None
    ratio = (sum(post_values) / len(post_values)) / normal_mean
    return _clamp(ratio, POST_HOLIDAY_FACTOR_MIN, POST_HOLIDAY_FACTOR_MAX)


def apply_post_holiday_adjustment(
    volume: float,
    target_day: date,
    volume_by_date: dict[str, float] | None,
) -> tuple[float, tuple[str, ...]]:
    if not is_post_holiday(target_day):
        return volume, ()
    factor = estimate_post_holiday_factor(target_day, volume_by_date)
    if factor is None:
        post_values = _same_weekday_post_holiday_values(target_day, volume_by_date)
        if len(post_values) < 1:
            return volume, ()
        reference = sum(post_values) / len(post_values)
        adjusted = volume * (1.0 - POST_HOLIDAY_BLEND_WEIGHT) + reference * POST_HOLIDAY_BLEND_WEIGHT
        return round(max(adjusted, 0.0), 1), (POST_HOLIDAY_LABEL,)
    return round(max(volume * factor, 0.0), 1), (POST_HOLIDAY_LABEL,)


def _same_weekday_post_holiday_values(
    target_day: date,
    volume_by_date: dict[str, float] | None,
) -> list[float]:
    if not volume_by_date:
        return []
    weekday = target_day.weekday()
    values: list[float] = []
    for weeks_back in range(1, POST_HOLIDAY_LOOKBACK_WEEKS + 1):
        candidate = target_day - timedelta(weeks=weeks_back)
        if candidate.weekday() != weekday or not is_post_holiday(candidate):
            continue
        value = volume_by_date.get(candidate.isoformat())
        if value is not None and value > 0:
            values.append(value)
    return values


def forecast_national_volume(
    *,
    target_day_type: str,
    seasonal_naive_1w: float | None = None,
    seasonal_naive_4w: float | None = None,
    same_type_baseline: float | None = None,
    same_type_avg_7d: float | None = None,
    today_volume: float | None = None,
    today_type_avg_7d: float | None = None,
) -> float | None:
    base, _ = _build_seasonal_ensemble(
        target_day_type=target_day_type,
        seasonal_naive_1w=seasonal_naive_1w,
        seasonal_naive_4w=seasonal_naive_4w,
        same_type_baseline=same_type_baseline,
        weekday_average=same_type_baseline,
    )
    if base is None:
        base = same_type_avg_7d or seasonal_naive_4w or seasonal_naive_1w
    if base is None:
        return None

    trend_reference = today_type_avg_7d if today_type_avg_7d is not None else same_type_avg_7d
    drift_factor = _damped_drift_factor(today_volume, trend_reference)
    combined_trend = 1.0 + (drift_factor - 1.0) * WEEKDAY_DRIFT_WEIGHT / 0.15
    return round(base * combined_trend, 1)


def _format_forecast_volume_lead(
    *,
    weekday_label: str,
    day_type_label: str,
    target_hint: str,
    forecast_volume: float,
    forecast_national_volume: float | None,
) -> str:
    volume_part = f"예상 처리물량은 약 {forecast_volume:,.1f}천개"
    if forecast_national_volume is not None:
        volume_part += f", 예상 전국접수물량은 약 {forecast_national_volume:,.1f}천개"
    volume_part += "입니다."
    return f"전망일({weekday_label}·{day_type_label}){target_hint}{volume_part}"


def forecast_next_day_volume(
    report_date: str,
    *,
    today_volume: float | None,
    avg_7d_volume: float | None,
    avg_30d_volume: float | None = None,
    recent_7d_volumes: list[float | None] | None = None,
    weekday_volumes: list[float | None],
    weekday_sample_counts: list[int],
    tomorrow_day_type: str | None = None,
    forecast_target_date: str | None = None,
    forecast_target_note: str | None = None,
    same_type_baseline: float | None = None,
    same_type_avg_7d: float | None = None,
    same_type_avg_30d: float | None = None,
    same_type_recent_volumes: list[float | None] | None = None,
    same_type_sample_count: int = 0,
    today_type_avg_7d: float | None = None,
    seasonal_naive_1w: float | None = None,
    seasonal_naive_4w: float | None = None,
    national_seasonal_naive_1w: float | None = None,
    national_seasonal_naive_4w: float | None = None,
    same_type_national_baseline: float | None = None,
    same_type_national_avg_7d: float | None = None,
    today_national_volume: float | None = None,
    today_type_national_avg_7d: float | None = None,
    operation_periods: list[dict] | None = None,
    historical_no_parcel_avg: float | None = None,
    volume_by_date: dict[str, float] | None = None,
    national_volume_by_date: dict[str, float] | None = None,
) -> VolumeForecastResult | None:
    report_day = date.fromisoformat(report_date)
    target = (
        date.fromisoformat(forecast_target_date)
        if forecast_target_date
        else resolve_forecast_target_date(report_day)
    )
    target_idx = target.weekday()
    resolved_day_type = tomorrow_day_type or resolve_day_type(target)
    target_note = forecast_target_note or forecast_target_note_for(report_day, target)

    weekday_average = (
        weekday_volumes[target_idx] if target_idx < len(weekday_volumes) else None
    )
    weekday_sample_count = (
        weekday_sample_counts[target_idx]
        if target_idx < len(weekday_sample_counts)
        else 0
    )

    use_same_type = (
        same_type_baseline is not None
        or same_type_avg_7d is not None
        or seasonal_naive_1w is not None
        or seasonal_naive_4w is not None
    )

    if use_same_type:
        weekday_average = same_type_baseline or weekday_average
        weekday_sample_count = same_type_sample_count or weekday_sample_count
        avg_7d_volume = same_type_avg_7d
        avg_30d_volume = same_type_avg_30d
        recent_7d_volumes = same_type_recent_volumes

    recent_3d_average = None
    if recent_7d_volumes:
        recent_values = [value for value in recent_7d_volumes if value is not None]
        if len(recent_values) >= 3:
            recent_3d_average = sum(recent_values[-3:]) / 3

    base, method = _build_seasonal_ensemble(
        target_day_type=resolved_day_type,
        seasonal_naive_1w=seasonal_naive_1w,
        seasonal_naive_4w=seasonal_naive_4w,
        same_type_baseline=same_type_baseline,
        weekday_average=weekday_average,
    )

    if base is None:
        base = _build_fallback_ensemble(
            weekday_average=weekday_average,
            weekday_sample_count=weekday_sample_count,
            avg_7d_volume=avg_7d_volume,
            avg_30d_volume=avg_30d_volume,
            recent_3d_average=recent_3d_average,
        )
        method = "fallback_blend"

    if base is None:
        return None

    trend_reference = today_type_avg_7d if use_same_type and today_type_avg_7d is not None else avg_7d_volume

    drift_factor = _damped_drift_factor(today_volume, trend_reference)
    if method.startswith("seasonal_naive"):
        combined_trend = 1.0 + (drift_factor - 1.0) * WEEKDAY_DRIFT_WEIGHT / 0.15
    else:
        trend_factor = 1.0
        if today_volume is not None and trend_reference not in (None, 0):
            trend_factor = _clamp(today_volume / trend_reference, TREND_FACTOR_MIN, TREND_FACTOR_MAX)
        momentum_factor = 1.0
        if recent_3d_average is not None and trend_reference not in (None, 0):
            momentum_factor = _clamp(
                recent_3d_average / trend_reference,
                MOMENTUM_FACTOR_MIN,
                MOMENTUM_FACTOR_MAX,
            )
        combined_trend = (
            (trend_factor + momentum_factor) / 2
            if today_volume is not None
            else momentum_factor
        )
        drift_factor = combined_trend

    forecast_volume = round(base * combined_trend, 1)
    forecast_volume, period_labels = apply_operation_period_volume_adjustment(
        forecast_volume,
        target,
        operation_periods or [],
        historical_no_parcel_avg=historical_no_parcel_avg,
        volume_by_date=volume_by_date,
        before_date=target,
    )
    forecast_volume, holiday_labels = apply_post_holiday_adjustment(
        forecast_volume,
        target,
        volume_by_date,
    )
    period_labels = period_labels + holiday_labels

    national_forecast = forecast_national_volume(
        target_day_type=resolved_day_type,
        seasonal_naive_1w=national_seasonal_naive_1w,
        seasonal_naive_4w=national_seasonal_naive_4w,
        same_type_baseline=same_type_national_baseline,
        same_type_avg_7d=same_type_national_avg_7d,
        today_volume=today_national_volume,
        today_type_avg_7d=today_type_national_avg_7d,
    )
    if national_forecast is not None:
        national_forecast, national_period_labels = apply_operation_period_volume_adjustment(
            national_forecast,
            target,
            operation_periods or [],
            volume_by_date=national_volume_by_date,
            before_date=target,
            include_no_parcel=False,
        )
        national_forecast, national_holiday_labels = apply_post_holiday_adjustment(
            national_forecast,
            target,
            national_volume_by_date or volume_by_date,
        )
        period_labels = tuple(dict.fromkeys(period_labels + national_period_labels + national_holiday_labels))

    seasonal_samples = same_type_sample_count or weekday_sample_count
    if seasonal_samples >= 4 and seasonal_naive_4w is not None and seasonal_naive_1w is not None:
        confidence = "high"
    elif seasonal_samples >= 2 or seasonal_naive_1w is not None:
        confidence = "medium"
    else:
        confidence = "low"

    trend_factor_out = drift_factor if method.startswith("seasonal_naive") else (
        _clamp(today_volume / trend_reference, TREND_FACTOR_MIN, TREND_FACTOR_MAX)
        if today_volume is not None and trend_reference not in (None, 0)
        else 1.0
    )
    momentum_factor_out = (
        _clamp(recent_3d_average / trend_reference, MOMENTUM_FACTOR_MIN, MOMENTUM_FACTOR_MAX)
        if recent_3d_average is not None and trend_reference not in (None, 0)
        else 1.0
    )

    return VolumeForecastResult(
        tomorrow_date=target.isoformat(),
        tomorrow_weekday_label=WEEKDAY_LABELS[target_idx],
        tomorrow_day_type=resolved_day_type,
        forecast_volume=forecast_volume,
        weekday_average=weekday_average,
        recent_7d_average=avg_7d_volume,
        recent_30d_average=avg_30d_volume,
        recent_3d_average=recent_3d_average,
        today_volume=today_volume,
        weekday_sample_count=weekday_sample_count,
        trend_factor=round(trend_factor_out, 3),
        momentum_factor=round(momentum_factor_out, 3),
        recent_trend_direction=_recent_trend_direction(recent_7d_volumes or []),
        confidence=confidence,
        forecast_target_note=target_note,
        seasonal_naive_1w=seasonal_naive_1w,
        seasonal_naive_4w=seasonal_naive_4w,
        forecast_method=method,
        operation_period_labels=period_labels,
        forecast_national_volume=national_forecast,
    )


def build_volume_forecast_text(result: VolumeForecastResult) -> str:
    day_type_label = DAY_TYPE_LABELS.get(result.tomorrow_day_type, result.tomorrow_day_type)
    target_hint = (
        f"({result.forecast_target_note}) "
        if result.forecast_target_note
        else ""
    )
    lead = _format_forecast_volume_lead(
        weekday_label=result.tomorrow_weekday_label,
        day_type_label=day_type_label,
        target_hint=target_hint,
        forecast_volume=result.forecast_volume,
        forecast_national_volume=result.forecast_national_volume,
    )

    detail_parts: list[str] = []
    if result.seasonal_naive_1w is not None:
        detail_parts.append(
            f"직전 동일 요일(Seasonal Naive) {result.seasonal_naive_1w:,.1f}천개"
        )
    if result.seasonal_naive_4w is not None:
        detail_parts.append(
            f"동일 요일 최근 4주 평균 {result.seasonal_naive_4w:,.1f}천개"
        )
    if result.weekday_average is not None and result.weekday_sample_count > 0:
        scope = (
            f"동일 유형({day_type_label})"
            if result.tomorrow_day_type != "weekday"
            else f"동일 요일({result.tomorrow_weekday_label})"
        )
        detail_parts.append(
            f"{scope} 장기 평균 {result.weekday_average:,.1f}천개"
            f"(표본 {result.weekday_sample_count}일)"
        )

    if detail_parts:
        basis = ", ".join(detail_parts)
    else:
        basis = "가용한 과거 데이터"

    method_note = (
        "요일 계절성(Seasonal Naive) 앙상블"
        if result.forecast_method.startswith("seasonal_naive")
        else "과거 평균 블렌드"
    )

    trend_notes: list[str] = []
    if result.recent_trend_direction:
        trend_notes.append(f"최근 동일 요일 추이는 {result.recent_trend_direction}")
    if result.today_volume is not None and result.trend_factor != 1.0:
        direction = "높은" if result.trend_factor > 1 else "낮은"
        trend_notes.append(f"오늘 물량은 동일 유형 7일 평균 대비 {direction} 수준")

    if trend_notes:
        return (
            f"{lead} {method_note}({basis})와 {', '.join(trend_notes)}을 반영한 추정치입니다."
            f"{format_forecast_adjustment_suffix(result.operation_period_labels)}"
        )
    return (
        f"{lead} {method_note}({basis})를 기반으로 산출한 추정치입니다."
        f"{format_forecast_adjustment_suffix(result.operation_period_labels)}"
    )


def format_forecast_adjustment_suffix(labels: tuple[str, ...]) -> str:
    if not labels:
        return ""
    calendar = [label for label in labels if label == POST_HOLIDAY_LABEL]
    operations = [label for label in labels if label != POST_HOLIDAY_LABEL]
    parts: list[str] = []
    if operations:
        parts.append(f"등록된 운영 특이 일정({', '.join(operations)})을 반영했습니다.")
    if calendar:
        parts.append("휴일 다음날 특성을 반영했습니다.")
    return " " + " ".join(parts)


def _accuracy_clause(forecast_volume: float, actual_volume: float, label: str) -> str:
    diff = actual_volume - forecast_volume
    diff_pct = abs(diff) / actual_volume * 100
    direction = "높게" if diff < 0 else "낮게"
    if diff_pct < 5:
        return (
            f"{label} 예측 {forecast_volume:,.1f}천개, 실제 {actual_volume:,.1f}천개로 "
            f"오차 약 {diff_pct:.1f}%"
        )
    return (
        f"{label} 예측 {forecast_volume:,.1f}천개, 실제 {actual_volume:,.1f}천개로 "
        f"약 {diff_pct:.1f}% {direction} 예측"
    )


def build_forecast_accuracy_text(
    forecast_volume: float,
    actual_volume: float,
    *,
    forecast_date: str,
    forecast_national_volume: float | None = None,
    actual_national_volume: float | None = None,
    source_label: str = "전일 예측",
) -> str:
    if actual_volume <= 0:
        return ""
    processing = _accuracy_clause(forecast_volume, actual_volume, "처리물량")
    national = ""
    if (
        forecast_national_volume is not None
        and actual_national_volume is not None
        and actual_national_volume > 0
    ):
        national = "; " + _accuracy_clause(
            forecast_national_volume,
            actual_national_volume,
            "전국접수물량",
        )
    similar = abs(actual_volume - forecast_volume) / actual_volume * 100 < 5
    ending = " — 예측과 유사했습니다." if similar and not national else "되었습니다."
    if national and similar:
        ending = "입니다."
    return f"당일({forecast_date}) {source_label} {processing}{national}{ending}"


def summarize_forecast_accuracy(rows: list[dict]) -> dict | None:
    processing_errors: list[float] = []
    national_errors: list[float] = []
    weekday_errors: list[float] = []
    holiday_errors: list[float] = []
    for row in rows:
        forecast = row.get("forecastVolume")
        actual = row.get("actualVolume")
        if forecast is None or actual in (None, 0):
            continue
        error = abs(forecast - actual) / actual * 100
        processing_errors.append(error)
        target = row.get("targetDate")
        if target:
            target_day = date.fromisoformat(target)
            if is_post_holiday(target_day):
                holiday_errors.append(error)
            else:
                weekday_errors.append(error)
        national_forecast = row.get("forecastNationalVolume")
        national_actual = row.get("actualNationalVolume")
        if national_forecast is not None and national_actual not in (None, 0):
            national_errors.append(abs(national_forecast - national_actual) / national_actual * 100)
    if len(processing_errors) < 3:
        return None
    return {
        "sampleCount": len(processing_errors),
        "processingMape": round(sum(processing_errors) / len(processing_errors), 1),
        "nationalMape": (
            round(sum(national_errors) / len(national_errors), 1) if national_errors else None
        ),
        "nationalSampleCount": len(national_errors),
        "weekdayMape": (
            round(sum(weekday_errors) / len(weekday_errors), 1) if weekday_errors else None
        ),
        "postHolidayMape": (
            round(sum(holiday_errors) / len(holiday_errors), 1) if holiday_errors else None
        ),
        "postHolidaySampleCount": len(holiday_errors),
    }


def build_forecast_accuracy_window_text(summary: dict | None) -> str:
    if not summary:
        return ""
    text = (
        f"최근 {summary['sampleCount']}일 저장 예측 기준 처리물량 MAPE 약 "
        f"{summary['processingMape']:.1f}%"
    )
    if summary.get("nationalMape") is not None:
        text += (
            f", 전국접수물량 MAPE 약 {summary['nationalMape']:.1f}%"
            f"({summary['nationalSampleCount']}일)"
        )
    extras: list[str] = []
    if summary.get("weekdayMape") is not None:
        extras.append(f"일반일 {summary['weekdayMape']:.1f}%")
    if summary.get("postHolidayMape") is not None and summary.get("postHolidaySampleCount", 0) > 0:
        extras.append(
            f"휴일 다음날 {summary['postHolidayMape']:.1f}%"
            f"({summary['postHolidaySampleCount']}일)"
        )
    if extras:
        text += f" — {', '.join(extras)}"
    return text + "입니다."


def estimate_staff_for_volume(
    forecast_volume: float,
    reference_volume: float | None,
    reference_staff: float | None,
) -> float | None:
    if reference_volume in (None, 0) or reference_staff is None:
        return None
    return round(reference_staff * (forecast_volume / reference_volume), 1)
