from __future__ import annotations

from datetime import date
from pathlib import Path

from domain.forecast_router import (
    VolumeForecastOutcome,
    is_weekday_target,
    resolve_feature_anchor_report,
    resolve_forecast_anchor_for_target,
)
from domain.volume_forecast import (
    build_volume_forecast_text,
    forecast_next_day_volume,
    resolve_forecast_target_date,
)
from domain.volume_ml_forecast import (
    VolumeMlForecastResult,
    build_ml_volume_forecast_text,
)
from application.volume_ml_forecast_service import VolumeMlForecastService
from infrastructure.db.sqlite_repository import SqliteRepository


class VolumeForecastService:
    def __init__(
        self,
        repository: SqliteRepository,
        *,
        model_cache_path: str | Path | None = None,
    ) -> None:
        self.repository = repository
        self.ml_service = VolumeMlForecastService(
            repository,
            model_cache_path=model_cache_path,
        )

    def predict(self, report_date: str, *, use_cache: bool = True) -> VolumeForecastOutcome | None:
        forecast_ctx = self.repository.get_volume_forecast_context(report_date)
        target_day_type = forecast_ctx.get("tomorrowDayType") or "weekday"
        target_date = forecast_ctx.get("forecastTargetDate") or resolve_forecast_target_date(
            date.fromisoformat(report_date)
        ).isoformat()

        if is_weekday_target(target_day_type):
            ml_result = self.ml_service.predict(
                report_date,
                seasonal_naive_4w=forecast_ctx.get("seasonalNaive4w"),
                use_cache=use_cache,
            )
            if ml_result is not None:
                return self._from_ml(ml_result)

        rule_result = self._predict_rule(report_date, forecast_ctx)
        if rule_result is None:
            return None
        return VolumeForecastOutcome(
            report_date=report_date,
            target_date=target_date,
            target_day_type=target_day_type,
            forecast_volume=rule_result.forecast_volume,
            method=rule_result.forecast_method,
            method_label="규칙 기반",
            seasonal_naive_4w=rule_result.seasonal_naive_4w,
            operation_period_labels=rule_result.operation_period_labels,
        )

    def predict_for_target(self, target_date: str, *, use_cache: bool = True) -> VolumeForecastOutcome | None:
        """전일 예측 검증용: 전망 대상일에 대한 예측을 역산 anchor에서 재생산한다."""
        target_day = date.fromisoformat(target_date)
        anchor_day = resolve_forecast_anchor_for_target(target_day)
        anchor_date = anchor_day.isoformat()
        report_dates = self.repository.list_report_dates()
        feature_anchor = resolve_feature_anchor_report(report_dates, anchor_day) or anchor_date

        anchor_ctx = self.repository.get_volume_forecast_context(anchor_date)
        target_day_type = resolve_day_type_for_context(anchor_ctx, target_day)

        if is_weekday_target(target_day_type):
            ml_result = self.ml_service.predict(
                anchor_date,
                feature_anchor_date=feature_anchor,
                seasonal_naive_4w=anchor_ctx.get("seasonalNaive4w"),
                use_cache=use_cache,
            )
            if ml_result is not None and ml_result.target_date == target_date:
                return self._from_ml(ml_result)

        volume = self.repository.get_volume_analysis(feature_anchor)
        if not volume:
            volume = self.repository.get_volume_analysis(anchor_date)
        if not volume:
            return None

        prior_ctx = anchor_ctx
        volume_summary = volume.get("summary", {})
        volume_benchmarks = volume.get("benchmarks", {})
        weekday_trend = volume.get("trends", {}).get("weekday", {})
        rule_result = forecast_next_day_volume(
            anchor_date,
            today_volume=prior_ctx.get("todayVolume") or volume_summary.get("totalVolume"),
            avg_7d_volume=volume_benchmarks.get("avg7d", {}).get("totalVolume"),
            avg_30d_volume=volume_benchmarks.get("avg30d", {}).get("totalVolume"),
            recent_7d_volumes=volume.get("trends", {}).get("7d", {}).get("totalVolume"),
            weekday_volumes=weekday_trend.get("totalVolume", []),
            weekday_sample_counts=weekday_trend.get("sampleCounts", []),
            tomorrow_day_type=prior_ctx.get("tomorrowDayType"),
            forecast_target_date=prior_ctx.get("forecastTargetDate"),
            forecast_target_note=prior_ctx.get("forecastTargetNote"),
            same_type_baseline=prior_ctx.get("sameTypeBaseline"),
            same_type_avg_7d=prior_ctx.get("sameTypeAvg7d"),
            same_type_avg_30d=prior_ctx.get("sameTypeAvg30d"),
            same_type_recent_volumes=prior_ctx.get("sameTypeRecent7d"),
            same_type_sample_count=prior_ctx.get("sameTypeSampleCount", 0),
            today_type_avg_7d=prior_ctx.get("todayTypeAvg7d"),
            seasonal_naive_1w=prior_ctx.get("seasonalNaive1w"),
            seasonal_naive_4w=prior_ctx.get("seasonalNaive4w"),
            national_seasonal_naive_1w=prior_ctx.get("nationalSeasonalNaive1w"),
            national_seasonal_naive_4w=prior_ctx.get("nationalSeasonalNaive4w"),
            same_type_national_baseline=prior_ctx.get("sameTypeNationalBaseline"),
            same_type_national_avg_7d=prior_ctx.get("sameTypeNationalAvg7d"),
            today_national_volume=prior_ctx.get("todayNationalVolume"),
            today_type_national_avg_7d=prior_ctx.get("todayTypeNationalAvg7d"),
            operation_periods=prior_ctx.get("operationPeriods"),
            historical_no_parcel_avg=prior_ctx.get("historicalNoParcelAvg"),
            volume_by_date=prior_ctx.get("volumeByDate"),
        )
        if rule_result is None or rule_result.tomorrow_date != target_date:
            return None
        return VolumeForecastOutcome(
            report_date=anchor_date,
            target_date=target_date,
            target_day_type=rule_result.tomorrow_day_type,
            forecast_volume=rule_result.forecast_volume,
            method=rule_result.forecast_method,
            method_label="규칙 기반",
            seasonal_naive_4w=rule_result.seasonal_naive_4w,
            operation_period_labels=rule_result.operation_period_labels,
        )

    def build_forecast_text(self, report_date: str) -> str | None:
        outcome = self.predict(report_date)
        if outcome is None:
            return None
        if outcome.method.startswith("ml"):
            ml_result = self.ml_service.predict(
                report_date,
                seasonal_naive_4w=self.repository.get_volume_forecast_context(report_date).get(
                    "seasonalNaive4w"
                ),
            )
            if ml_result is not None:
                return build_ml_volume_forecast_text(ml_result)
        rule_result = self._predict_rule(
            report_date,
            self.repository.get_volume_forecast_context(report_date),
        )
        if rule_result is None:
            return None
        method_suffix = f" [{outcome.method_label}]"
        return build_volume_forecast_text(rule_result) + method_suffix

    def _predict_rule(self, report_date: str, forecast_ctx: dict):
        volume = self.repository.get_volume_analysis(report_date)
        if not volume:
            return None
        volume_summary = volume.get("summary", {})
        volume_benchmarks = volume.get("benchmarks", {})
        weekday_trend = volume.get("trends", {}).get("weekday", {})
        return forecast_next_day_volume(
            report_date,
            today_volume=forecast_ctx.get("todayVolume") or volume_summary.get("totalVolume"),
            avg_7d_volume=volume_benchmarks.get("avg7d", {}).get("totalVolume"),
            avg_30d_volume=volume_benchmarks.get("avg30d", {}).get("totalVolume"),
            recent_7d_volumes=volume.get("trends", {}).get("7d", {}).get("totalVolume"),
            weekday_volumes=weekday_trend.get("totalVolume", []),
            weekday_sample_counts=weekday_trend.get("sampleCounts", []),
            tomorrow_day_type=forecast_ctx.get("tomorrowDayType"),
            forecast_target_date=forecast_ctx.get("forecastTargetDate"),
            forecast_target_note=forecast_ctx.get("forecastTargetNote"),
            same_type_baseline=forecast_ctx.get("sameTypeBaseline"),
            same_type_avg_7d=forecast_ctx.get("sameTypeAvg7d"),
            same_type_avg_30d=forecast_ctx.get("sameTypeAvg30d"),
            same_type_recent_volumes=forecast_ctx.get("sameTypeRecent7d"),
            same_type_sample_count=forecast_ctx.get("sameTypeSampleCount", 0),
            today_type_avg_7d=forecast_ctx.get("todayTypeAvg7d"),
            seasonal_naive_1w=forecast_ctx.get("seasonalNaive1w"),
            seasonal_naive_4w=forecast_ctx.get("seasonalNaive4w"),
            national_seasonal_naive_1w=forecast_ctx.get("nationalSeasonalNaive1w"),
            national_seasonal_naive_4w=forecast_ctx.get("nationalSeasonalNaive4w"),
            same_type_national_baseline=forecast_ctx.get("sameTypeNationalBaseline"),
            same_type_national_avg_7d=forecast_ctx.get("sameTypeNationalAvg7d"),
            today_national_volume=forecast_ctx.get("todayNationalVolume"),
            today_type_national_avg_7d=forecast_ctx.get("todayTypeNationalAvg7d"),
            operation_periods=forecast_ctx.get("operationPeriods"),
            historical_no_parcel_avg=forecast_ctx.get("historicalNoParcelAvg"),
            volume_by_date=forecast_ctx.get("volumeByDate"),
        )

    @staticmethod
    def _from_ml(result: VolumeMlForecastResult) -> VolumeForecastOutcome:
        return VolumeForecastOutcome(
            report_date=result.report_date,
            target_date=result.target_date,
            target_day_type=result.target_day_type,
            forecast_volume=result.forecast_volume,
            method=result.method,
            method_label=result.method_label,
            seasonal_naive_4w=result.seasonal_naive_4w,
            ml_volume=result.ml_volume,
            bias_adjustment=result.bias_adjustment,
            operation_period_labels=result.operation_period_labels,
        )


def resolve_day_type_for_context(anchor_ctx: dict, target_day: date) -> str:
    from domain.day_type import resolve_day_type

    return anchor_ctx.get("tomorrowDayType") or resolve_day_type(target_day)
