from __future__ import annotations

from datetime import date
from pathlib import Path

from domain.volume_ml_forecast import (
    VolumeMlForecastResult,
    VolumeMlRow,
    build_ml_volume_forecast_text,
    predict_next_volume,
)
from infrastructure.db.sqlite_repository import SqliteRepository


class VolumeMlForecastService:
    def __init__(
        self,
        repository: SqliteRepository,
        *,
        model_cache_path: str | Path | None = None,
    ) -> None:
        self.repository = repository
        self.model_cache_path = Path(model_cache_path) if model_cache_path else None

    def predict(
        self,
        report_date: str,
        *,
        feature_anchor_date: str | None = None,
        seasonal_naive_4w: float | None = None,
        use_cache: bool = True,
    ) -> VolumeMlForecastResult | None:
        rows = self._load_rows(report_date)
        forecast_ctx = self.repository.get_volume_forecast_context(report_date)
        return predict_next_volume(
            rows,
            report_date,
            operation_periods=forecast_ctx.get("operationPeriods"),
            historical_no_parcel_avg=forecast_ctx.get("historicalNoParcelAvg"),
            feature_anchor_date=feature_anchor_date,
            seasonal_naive_4w=seasonal_naive_4w or forecast_ctx.get("seasonalNaive4w"),
            cache_path=self.model_cache_path,
            use_cache=use_cache,
        )

    def build_forecast_text(self, report_date: str) -> str | None:
        result = self.predict(report_date)
        if result is None:
            return None
        return build_ml_volume_forecast_text(result)

    def _load_rows(self, through_date: str) -> list[VolumeMlRow]:
        raw_rows = self.repository.get_volume_ml_timeseries(through_date)
        rows: list[VolumeMlRow] = []
        for row in raw_rows:
            rows.append(
                VolumeMlRow(
                    report_date=date.fromisoformat(row["reportDate"]),
                    total_volume=row.get("totalVolume"),
                    national_volume=row.get("nationalVolume"),
                    remaining_volume=row.get("remainingVolume"),
                    day_type=row.get("dayType"),
                    report_format=row.get("reportFormat"),
                )
            )
        return rows
