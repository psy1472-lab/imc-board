from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from datetime import date

from application.volume_forecast_service import VolumeForecastService
from domain.day_type import resolve_day_type
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
    high_pred = sum(1 for err in errors if err < 0)
    low_pred = sum(1 for err in errors if err > 0)
    print(f"=== {label} ===")
    print(f"검증 일수: {len(records)}")
    print(f"MAE: {statistics.mean([abs(err) for err in errors]):.1f}천")
    print(f"MAPE: {statistics.mean(pcts):.1f}%")
    print(f"오차 5% 이내: {within5}일 ({within5 / len(records) * 100:.1f}%)")
    print(f"높게 예측: {high_pred}일, 낮게 예측: {low_pred}일")
    print(f"평균 편향: {statistics.mean(errors):+.1f}천")
    worst = max(records, key=lambda item: item.error_pct)
    best = min(records, key=lambda item: item.error_pct)
    print(
        f"최대 오차: {worst.report_date} 예측 {worst.forecast:.1f} vs 실제 {worst.actual:.1f} "
        f"({worst.error_pct:.1f}%)"
    )
    print(
        f"최소 오차: {best.report_date} 예측 {best.forecast:.1f} vs 실제 {best.actual:.1f} "
        f"({best.error_pct:.1f}%)"
    )
    print()


def run_backtest(db_path: Path, year: str | None = None, use_cache: bool = False) -> None:
    repo = SqliteRepository(str(db_path))
    service = VolumeForecastService(
        repo,
        model_cache_path=db_path.parent / "models" / "volume_forecast_lgb.pkl",
    )
    report_dates = repo.list_report_dates()
    records: list[ValidationRecord] = []

    for report_date in report_dates:
        if year and not report_date.startswith(year):
            continue
        volume = repo.get_volume_analysis(report_date)
        if not volume:
            continue
        actual = volume.get("summary", {}).get("totalVolume")
        if actual is None:
            continue
        prior = service.predict_for_target(report_date, use_cache=use_cache)
        if prior is None:
            continue
        error = actual - prior.forecast_volume
        error_pct = abs(error) / actual * 100 if actual else 0.0
        day_type = resolve_day_type(date.fromisoformat(report_date))
        records.append(
            ValidationRecord(
                report_date=report_date,
                day_type=day_type,
                forecast=prior.forecast_volume,
                actual=actual,
                error=error,
                error_pct=error_pct,
                method=prior.method,
            )
        )

    if year:
        _summarize(records, f"{year}년 전체")
    else:
        _summarize(records, "전체")

    weekday = [record for record in records if record.day_type == "weekday"]
    non_weekday = [record for record in records if record.day_type != "weekday"]
    _summarize(weekday, "평일(weekday)")
    _summarize(non_weekday, "비평일")

    by_month: dict[str, list[ValidationRecord]] = defaultdict(list)
    for record in records:
        if record.day_type == "weekday":
            by_month[record.report_date[:7]].append(record)
    if by_month:
        print("=== 평일 월별 MAPE ===")
        for month in sorted(by_month):
            pcts = [item.error_pct for item in by_month[month]]
            within5 = sum(1 for pct in pcts if pct < 5)
            print(
                f"{month}: {len(pcts)}일, MAPE {statistics.mean(pcts):.1f}%, "
                f"5%이내 {within5 / len(pcts) * 100:.1f}%"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="전일 예측 백테스트")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "imc_dashboard.db",
    )
    parser.add_argument("--year", type=str, default=None, help="예: 2026")
    parser.add_argument("--use-cache", action="store_true")
    args = parser.parse_args()
    run_backtest(args.db, year=args.year, use_cache=args.use_cache)


if __name__ == "__main__":
    main()
