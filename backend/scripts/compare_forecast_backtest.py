"""개선 전(legacy) vs 개선 후(current) 전일 예측 백테스트 비교."""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from application.volume_forecast_service import VolumeForecastService
from application.volume_ml_forecast_service import VolumeMlForecastService
from domain.day_type import resolve_day_type
from domain.volume_forecast import forecast_next_day_volume
from infrastructure.db.sqlite_repository import SqliteRepository


@dataclass
class ValidationRecord:
    report_date: str
    day_type: str
    forecast: float
    actual: float
    error: float
    error_pct: float
    method: str


def _summarize(records: list[ValidationRecord], label: str) -> None:
    if not records:
        print(f"{label}: 검증 가능 일수 0")
        return
    errors = [record.error for record in records]
    pcts = [record.error_pct for record in records]
    within5 = sum(1 for pct in pcts if pct < 5)
    print(f"=== {label} ===")
    print(f"검증 일수: {len(records)}")
    print(f"MAE: {statistics.mean([abs(err) for err in errors]):.1f}천")
    print(f"MAPE: {statistics.mean(pcts):.1f}%")
    print(f"오차 5% 이내: {within5}일 ({within5 / len(records) * 100:.1f}%)")
    print(f"평균 편향: {statistics.mean(errors):+.1f}천")
    print()


def _legacy_rule_forecast(
    repository: SqliteRepository,
    prior_date: str,
    target_date: str,
) -> float | None:
    prior_ctx = repository.get_volume_forecast_context(prior_date)
    volume = repository.get_volume_analysis(prior_date)
    if not volume:
        return None

    volume_summary = volume.get("summary", {})
    volume_benchmarks = volume.get("benchmarks", {})
    weekday_trend = volume.get("trends", {}).get("weekday", {})
    rule_result = forecast_next_day_volume(
        prior_date,
        today_volume=prior_ctx.get("todayVolume") or volume_summary.get("totalVolume"),
        avg_7d_volume=volume_benchmarks.get("avg7d", {}).get("totalVolume"),
        avg_30d_volume=volume_benchmarks.get("avg30d", {}).get("totalVolume"),
        recent_7d_volumes=volume.get("trends", {}).get("7d", {}).get("totalVolume"),
        weekday_volumes=weekday_trend.get("totalVolume", []),
        weekday_sample_counts=weekday_trend.get("sampleCounts", []),
        tomorrow_day_type=prior_ctx.get("tomorrowDayType"),
        forecast_target_date=prior_ctx.get("forecastTargetDate") or target_date,
        forecast_target_note=prior_ctx.get("forecastTargetNote"),
        same_type_baseline=prior_ctx.get("sameTypeBaseline"),
        same_type_avg_7d=prior_ctx.get("sameTypeAvg7d"),
        same_type_avg_30d=prior_ctx.get("sameTypeAvg30d"),
        same_type_recent_volumes=prior_ctx.get("sameTypeRecent7d"),
        same_type_sample_count=prior_ctx.get("sameTypeSampleCount", 0),
        today_type_avg_7d=prior_ctx.get("todayTypeAvg7d"),
        seasonal_naive_1w=prior_ctx.get("seasonalNaive1w"),
        seasonal_naive_4w=prior_ctx.get("seasonalNaive4w"),
        operation_periods=prior_ctx.get("operationPeriods"),
        historical_no_parcel_avg=prior_ctx.get("historicalNoParcelAvg"),
    )
    if rule_result is None:
        return None
    if rule_result.tomorrow_date != target_date:
        return None
    return rule_result.forecast_volume


def legacy_prior_forecast(
    repository: SqliteRepository,
    ml_service: VolumeMlForecastService,
    report_date: str,
    *,
    use_cache: bool,
) -> tuple[float | None, str]:
    """개선 전: 전일(calendar -1) anchor, 요일 분기 없이 ML 우선."""
    prior_date = (date.fromisoformat(report_date) - timedelta(days=1)).isoformat()
    prior_ctx = repository.get_volume_forecast_context(prior_date)

    ml_result = ml_service.predict(
        prior_date,
        seasonal_naive_4w=prior_ctx.get("seasonalNaive4w"),
        use_cache=use_cache,
    )
    if ml_result is not None and ml_result.target_date == report_date:
        return ml_result.forecast_volume, ml_result.method

    rule_volume = _legacy_rule_forecast(repository, prior_date, report_date)
    if rule_volume is not None:
        return rule_volume, "rule_legacy"

    return None, "none"


def collect_records(
    repository: SqliteRepository,
    year: str | None,
    predictor,
    *,
    use_cache: bool,
) -> list[ValidationRecord]:
    records: list[ValidationRecord] = []
    for report_date in repository.list_report_dates():
        if year and not report_date.startswith(year):
            continue
        volume = repository.get_volume_analysis(report_date)
        if not volume:
            continue
        actual = volume.get("summary", {}).get("totalVolume")
        if actual is None:
            continue

        forecast, method = predictor(report_date, use_cache=use_cache)
        if forecast is None:
            continue

        error = actual - forecast
        error_pct = abs(error) / actual * 100 if actual else 0.0
        records.append(
            ValidationRecord(
                report_date=report_date,
                day_type=resolve_day_type(date.fromisoformat(report_date)),
                forecast=forecast,
                actual=actual,
                error=error,
                error_pct=error_pct,
                method=method,
            )
        )
    return records


def _compare_weekday(before: list[ValidationRecord], after: list[ValidationRecord]) -> None:
    before_weekday = [r for r in before if r.day_type == "weekday"]
    after_weekday = [r for r in after if r.day_type == "weekday"]
    if not before_weekday or not after_weekday:
        return

    before_mape = statistics.mean(r.error_pct for r in before_weekday)
    after_mape = statistics.mean(r.error_pct for r in after_weekday)
    before_hit = sum(1 for r in before_weekday if r.error_pct < 5) / len(before_weekday) * 100
    after_hit = sum(1 for r in after_weekday if r.error_pct < 5) / len(after_weekday) * 100

    print("=== 평일(weekday) 개선 전후 비교 ===")
    print(f"검증 일수: {len(before_weekday)}일 (동일)")
    print(f"MAPE: {before_mape:.1f}% → {after_mape:.1f}%  ({after_mape - before_mape:+.1f}%p)")
    print(f"5% 이내: {before_hit:.1f}% → {after_hit:.1f}%  ({after_hit - before_hit:+.1f}%p)")
    print(
        f"MAE: {statistics.mean(abs(r.error) for r in before_weekday):.1f}천 "
        f"→ {statistics.mean(abs(r.error) for r in after_weekday):.1f}천"
    )
    print(
        f"편향: {statistics.mean(r.error for r in before_weekday):+.1f}천 "
        f"→ {statistics.mean(r.error for r in after_weekday):+.1f}천"
    )
    print()


def run_compare(db_path: Path, year: str | None, use_cache: bool) -> None:
    repository = SqliteRepository(str(db_path))
    cache_path = db_path.parent / "models" / "volume_forecast_lgb.pkl"
    ml_service = VolumeMlForecastService(repository, model_cache_path=cache_path)
    current_service = VolumeForecastService(repository, model_cache_path=cache_path)

    def predict_legacy(report_date: str, *, use_cache: bool) -> tuple[float | None, str]:
        return legacy_prior_forecast(repository, ml_service, report_date, use_cache=use_cache)

    def predict_current(report_date: str, *, use_cache: bool) -> tuple[float | None, str]:
        outcome = current_service.predict_for_target(report_date, use_cache=use_cache)
        if outcome is None:
            return None, "none"
        return outcome.forecast_volume, outcome.method

    legacy_records = collect_records(
        repository,
        year,
        lambda report_date, use_cache=use_cache: predict_legacy(report_date, use_cache=use_cache),
        use_cache=use_cache,
    )
    current_records = collect_records(
        repository,
        year,
        lambda report_date, use_cache=use_cache: predict_current(report_date, use_cache=use_cache),
        use_cache=use_cache,
    )

    label = f"{year}년 " if year else ""
    print(f"# {label}전일 예측 A/B 비교 (로컬 DB: {db_path.name})\n")
    _summarize(legacy_records, f"{label}개선 전 (legacy prior)")
    _summarize(current_records, f"{label}개선 후 (current router)")

    legacy_weekday = [r for r in legacy_records if r.day_type == "weekday"]
    current_weekday = [r for r in current_records if r.day_type == "weekday"]
    _summarize(legacy_weekday, f"{label}개선 전 · 평일")
    _summarize(current_weekday, f"{label}개선 후 · 평일")
    _compare_weekday(legacy_records, current_records)

    by_month: dict[str, list[tuple[float, float]]] = defaultdict(list)
    legacy_map = {r.report_date: r for r in legacy_weekday}
    for record in current_weekday:
        legacy = legacy_map.get(record.report_date)
        if legacy is None:
            continue
        by_month[record.report_date[:7]].append((legacy.error_pct, record.error_pct))

    if by_month:
        print("=== 평일 월별 MAPE (개선 전 → 개선 후) ===")
        for month in sorted(by_month):
            pairs = by_month[month]
            before = statistics.mean(left for left, _ in pairs)
            after = statistics.mean(right for _, right in pairs)
            print(f"{month}: {len(pairs)}일, {before:.1f}% → {after:.1f}% ({after - before:+.1f}%p)")


def main() -> None:
    parser = argparse.ArgumentParser(description="전일 예측 개선 전후 A/B 백테스트")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "imc_dashboard.db",
    )
    parser.add_argument("--year", type=str, default="2026")
    parser.add_argument("--use-cache", action="store_true")
    args = parser.parse_args()
    run_compare(args.db, year=args.year, use_cache=args.use_cache)


if __name__ == "__main__":
    main()
