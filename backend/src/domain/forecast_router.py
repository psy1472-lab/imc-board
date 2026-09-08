from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from domain.day_type import resolve_day_type
from domain.volume_forecast import resolve_forecast_target_date

if TYPE_CHECKING:
    from domain.volume_ml_forecast import VolumeMlForecastResult


@dataclass(frozen=True)
class VolumeForecastOutcome:
    report_date: str
    target_date: str
    target_day_type: str
    forecast_volume: float
    method: str
    method_label: str
    seasonal_naive_4w: float | None = None
    ml_volume: float | None = None
    bias_adjustment: float = 0.0
    operation_period_labels: tuple[str, ...] = ()
    ml_result: VolumeMlForecastResult | None = None
    forecast_national_volume: float | None = None


def is_weekday_target(day_type: str) -> bool:
    return day_type == "weekday"


def resolve_forecast_anchor_for_target(target_day: date) -> date:
    """전망 대상일에 대해 예측을 산출한 기준일(보고서 anchor)을 역산한다."""
    if target_day.weekday() == 6:
        return target_day - timedelta(days=2)
    return target_day - timedelta(days=1)


def find_last_report_on_or_before(report_dates: list[str], anchor: date) -> str | None:
    anchor_key = anchor.isoformat()
    candidates = [value for value in report_dates if value <= anchor_key]
    return candidates[-1] if candidates else None


def resolve_feature_anchor_report(report_dates: list[str], anchor_day: date) -> str | None:
    return find_last_report_on_or_before(report_dates, anchor_day)


def target_day_type_for_report(report_date: str) -> str:
    report_day = date.fromisoformat(report_date)
    target = resolve_forecast_target_date(report_day)
    return resolve_day_type(target)
