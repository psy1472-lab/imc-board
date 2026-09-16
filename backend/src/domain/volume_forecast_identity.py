from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from domain.day_type import resolve_day_type

PROCESSING_RATE_MIN_SAMPLES = 3
PROCESSING_RATE_LOOKBACK = 8
IDENTITY_RATE_RELATIVE_DEVIATION = 0.20
IDENTITY_ML_RESIDUAL_WEIGHT = 0.3


def processing_rate(volume: float | None, national: float | None) -> float | None:
    """전국대비처리율(%). 전국접수가 없으면 계산하지 않는다."""
    if volume is None or national in (None, 0):
        return None
    return round((volume / national) * 100, 2)


def implied_processing_rate(volume: float | None, national: float | None) -> float | None:
    return processing_rate(volume, national)


def compose_volume_from_national_and_rate(
    national: float | None,
    rate: float | None,
) -> float | None:
    if national is None or rate is None:
        return None
    return round(national * rate / 100.0, 1)


def build_processing_rate_history(
    volume_by_date: dict[str, float] | None,
    national_by_date: dict[str, float] | None,
    *,
    before_date: date | None = None,
    weekday_only: bool = True,
) -> list[tuple[date, float]]:
    if not volume_by_date or not national_by_date:
        return []
    history: list[tuple[date, float]] = []
    for key in sorted(volume_by_date):
        day = date.fromisoformat(key)
        if before_date is not None and day >= before_date:
            continue
        if weekday_only and resolve_day_type(day) != "weekday":
            continue
        rate = processing_rate(volume_by_date.get(key), national_by_date.get(key))
        if rate is None:
            continue
        history.append((day, rate))
    return history


def forecast_processing_rate(
    target_day: date,
    rate_history: list[tuple[date, float]],
    *,
    min_same_weekday_samples: int = PROCESSING_RATE_MIN_SAMPLES,
    lookback: int = PROCESSING_RATE_LOOKBACK,
) -> float | None:
    """전망일 요일의 최근 평일 처리율. 표본이 적으면 전체 평일 중앙값."""
    if not rate_history:
        return None
    same_weekday = [rate for day, rate in rate_history if day.weekday() == target_day.weekday()]
    recent = same_weekday[-lookback:] if same_weekday else []
    if len(recent) >= min_same_weekday_samples:
        return round(sum(recent) / len(recent), 2)
    all_rates = [rate for _, rate in rate_history]
    if not all_rates:
        return None
    return round(float(median(all_rates)), 2)


def reconcile_volume_identity(
    *,
    direct_volume: float | None,
    identity_volume: float | None,
    forecast_national: float | None = None,
    weekday_rate: float | None = None,
    relative_deviation: float = IDENTITY_RATE_RELATIVE_DEVIATION,
    prefer_identity: bool = True,
) -> tuple[float | None, str]:
    """직접 예측과 곱 예측을 맞춘다. 기본은 곱 예측, 없으면 직접 예측 폴백."""
    if identity_volume is None:
        return direct_volume, "direct"
    if direct_volume is None:
        return identity_volume, "identity"
    if prefer_identity:
        if forecast_national not in (None, 0) and weekday_rate not in (None, 0):
            implied = implied_processing_rate(direct_volume, forecast_national)
            if implied is not None:
                deviation = abs(implied - weekday_rate) / abs(weekday_rate)
                if deviation > relative_deviation:
                    return identity_volume, "identity_reconcile"
        return identity_volume, "identity"
    if forecast_national not in (None, 0) and weekday_rate not in (None, 0):
        implied = implied_processing_rate(direct_volume, forecast_national)
        if implied is not None:
            deviation = abs(implied - weekday_rate) / abs(weekday_rate)
            if deviation > relative_deviation:
                return identity_volume, "identity_reconcile"
    return direct_volume, "direct"


def impute_national_features(
    national_volume: float | None,
    *,
    prev_day_volume: float = 0.0,
    last_weekday_national: float | None = None,
    last_weekday_rate: float | None = None,
) -> tuple[float, float]:
    """예측 특성용 전국접수·비율. PDF KPI를 0으로 채우지 않고, 직전 평일 값만 빌려 쓴다."""
    if national_volume is not None and national_volume > 0:
        ratio = national_volume / prev_day_volume if prev_day_volume > 0 else 0.0
        return float(national_volume), float(ratio)
    if last_weekday_national is not None and last_weekday_national > 0:
        if last_weekday_rate not in (None, 0):
            ratio = 100.0 / last_weekday_rate
        elif prev_day_volume > 0:
            ratio = last_weekday_national / prev_day_volume
        else:
            ratio = 0.0
        return float(last_weekday_national), float(ratio)
    return 0.0, 0.0


def last_weekday_national_features(
    observations: list[tuple[date, float | None, float | None]],
    *,
    through: date,
) -> tuple[float | None, float | None]:
    last_national: float | None = None
    last_rate: float | None = None
    for day, volume, national in observations:
        if day > through:
            break
        if resolve_day_type(day) != "weekday":
            continue
        if national is not None and national > 0:
            last_national = national
        rate = processing_rate(volume, national)
        if rate is not None:
            last_rate = rate
    return last_national, last_rate


def _mape(actuals: list[float], forecasts: list[float]) -> float | None:
    pairs = [
        (actual, forecast)
        for actual, forecast in zip(actuals, forecasts)
        if actual not in (None, 0) and forecast is not None
    ]
    if not pairs:
        return None
    return round(sum(abs(forecast - actual) / actual * 100 for actual, forecast in pairs) / len(pairs), 1)


@dataclass(frozen=True)
class IdentityForecastPoint:
    target_date: str
    actual_volume: float
    actual_national: float | None
    actual_rate: float | None
    direct_volume: float | None
    identity_volume: float | None
    forecast_national: float | None
    forecast_rate: float | None


def walk_forward_identity_points(
    observations: list[tuple[str, float, float | None]],
    *,
    weekday_only: bool = True,
) -> list[IdentityForecastPoint]:
    """합성 시계열 홀드아웃: 직접=직전 동일 요일, 곱=직전 동일 요일 전국 × 요일 처리율."""
    parsed = [(date.fromisoformat(day), volume, national) for day, volume, national in observations]
    points: list[IdentityForecastPoint] = []
    for index, (target, actual_volume, actual_national) in enumerate(parsed):
        if weekday_only and resolve_day_type(target) != "weekday":
            continue
        prior_volume = {day.isoformat(): volume for day, volume, _ in parsed[:index]}
        prior_national = {
            day.isoformat(): national
            for day, _, national in parsed[:index]
            if national is not None
        }
        lag_key = (target - timedelta(days=7)).isoformat()
        direct = prior_volume.get(lag_key)
        forecast_national = prior_national.get(lag_key)
        history = build_processing_rate_history(prior_volume, prior_national, before_date=target)
        rate = forecast_processing_rate(target, history)
        identity = compose_volume_from_national_and_rate(forecast_national, rate)
        points.append(
            IdentityForecastPoint(
                target_date=target.isoformat(),
                actual_volume=actual_volume,
                actual_national=actual_national,
                actual_rate=processing_rate(actual_volume, actual_national),
                direct_volume=direct,
                identity_volume=identity,
                forecast_national=forecast_national,
                forecast_rate=rate,
            )
        )
    return points


def compare_identity_forecasts(points: list[IdentityForecastPoint]) -> dict | None:
    usable = [point for point in points if point.actual_volume not in (None, 0)]
    if len(usable) < 3:
        return None
    direct_pairs = [
        (point.actual_volume, point.direct_volume)
        for point in usable
        if point.direct_volume is not None
    ]
    identity_pairs = [
        (point.actual_volume, point.identity_volume)
        for point in usable
        if point.identity_volume is not None
    ]
    national_pairs = [
        (point.actual_national, point.forecast_national)
        for point in usable
        if point.actual_national not in (None, 0) and point.forecast_national is not None
    ]
    rate_pairs = [
        (point.actual_rate, point.forecast_rate)
        for point in usable
        if point.actual_rate not in (None, 0) and point.forecast_rate is not None
    ]
    direct_mape = _mape(
        [actual for actual, _ in direct_pairs],
        [forecast for _, forecast in direct_pairs],
    )
    identity_mape = _mape(
        [actual for actual, _ in identity_pairs],
        [forecast for _, forecast in identity_pairs],
    )
    prefer_identity = (
        identity_mape is not None
        and direct_mape is not None
        and identity_mape <= direct_mape
        and len(identity_pairs) >= 3
    )
    return {
        "sampleCount": len(usable),
        "directVolumeMape": direct_mape,
        "identityVolumeMape": identity_mape,
        "directSampleCount": len(direct_pairs),
        "identitySampleCount": len(identity_pairs),
        "nationalMape": _mape(
            [actual for actual, _ in national_pairs],
            [forecast for _, forecast in national_pairs],
        ),
        "nationalSampleCount": len(national_pairs),
        "rateMape": _mape(
            [actual for actual, _ in rate_pairs],
            [forecast for _, forecast in rate_pairs],
        ),
        "rateSampleCount": len(rate_pairs),
        "preferIdentity": prefer_identity,
    }
