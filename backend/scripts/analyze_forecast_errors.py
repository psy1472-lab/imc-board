from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from application.volume_forecast_service import VolumeForecastService
from domain.day_type import resolve_day_type
from domain.operation_period import (
    classify_forecast_period_category,
    get_operation_periods_for_date,
    operation_period_labels,
)
from domain.volume_forecast import resolve_forecast_target_date
from infrastructure.db.sqlite_repository import SqliteRepository


@dataclass
class ErrorRecord:
    report_date: str
    target_date: str
    forecast: float
    actual: float
    error: float
    error_pct: float
    method: str
    method_label: str
    day_type: str
    period_category: str
    period_labels: str
    direction: str


def _direction(error: float) -> str:
    if error > 0:
        return "과소예측"
    if error < 0:
        return "과대예측"
    return "일치"


def collect_errors(
    db_path: Path,
    *,
    year: str | None = None,
    weekday_only: bool = False,
    use_cache: bool = False,
) -> list[ErrorRecord]:
    repo = SqliteRepository(str(db_path))
    service = VolumeForecastService(
        repo,
        model_cache_path=db_path.parent / "models" / "volume_forecast_lgb.pkl",
    )
    operation_periods = repo.list_operation_periods()
    records: list[ErrorRecord] = []

    for report_date in repo.list_report_dates():
        if year and not report_date.startswith(year):
            continue
        volume = repo.get_volume_analysis(report_date)
        if not volume:
            continue
        actual = volume.get("summary", {}).get("totalVolume")
        if actual is None:
            continue
        day_type = resolve_day_type(date.fromisoformat(report_date))
        if weekday_only and day_type != "weekday":
            continue

        prior = service.predict_for_target(report_date, use_cache=use_cache)
        if prior is None:
            continue

        target_day = date.fromisoformat(prior.target_date)
        active = get_operation_periods_for_date(target_day, operation_periods)
        error = actual - prior.forecast_volume
        error_pct = abs(error) / actual * 100 if actual else 0.0
        records.append(
            ErrorRecord(
                report_date=report_date,
                target_date=prior.target_date,
                forecast=prior.forecast_volume,
                actual=actual,
                error=error,
                error_pct=error_pct,
                method=prior.method,
                method_label=prior.method_label,
                day_type=day_type,
                period_category=classify_forecast_period_category(target_day, operation_periods),
                period_labels=", ".join(operation_period_labels(active)) or "-",
                direction=_direction(error),
            )
        )
    return records


def _summarize_mape(records: list[ErrorRecord], label: str) -> str:
    if not records:
        return f"{label}: 검증 가능 일수 0"
    pcts = [record.error_pct for record in records]
    within5 = sum(1 for pct in pcts if pct < 5)
    lines = [
        f"=== {label} ===",
        f"검증 일수: {len(records)}",
        f"MAPE: {statistics.mean(pcts):.1f}%",
        f"오차 5% 이내: {within5}일 ({within5 / len(records) * 100:.1f}%)",
        f"평균 편향: {statistics.mean([record.error for record in records]):+.1f}천",
    ]
    return "\n".join(lines)


def format_report(records: list[ErrorRecord], top: int) -> str:
    lines: list[str] = []
    lines.append(_summarize_mape(records, "전체"))
    lines.append("")

    by_month: dict[str, list[ErrorRecord]] = defaultdict(list)
    for record in records:
        by_month[record.report_date[:7]].append(record)
    if by_month:
        lines.append("=== 월별 MAPE ===")
        for month in sorted(by_month):
            pcts = [item.error_pct for item in by_month[month]]
            within5 = sum(1 for pct in pcts if pct < 5)
            lines.append(
                f"{month}: {len(pcts)}일, MAPE {statistics.mean(pcts):.1f}%, "
                f"5%이내 {within5 / len(pcts) * 100:.1f}%"
            )
        lines.append("")

    by_category: dict[str, list[ErrorRecord]] = defaultdict(list)
    for record in records:
        by_category[record.period_category].append(record)
    lines.append("=== 기간 유형별 MAPE ===")
    for category in ("normal", "no_parcel", "special"):
        subset = by_category.get(category, [])
        if subset:
            lines.append(
                f"{category}: {len(subset)}일, MAPE {statistics.mean([r.error_pct for r in subset]):.1f}%"
            )
    lines.append("")

    by_method: dict[str, list[ErrorRecord]] = defaultdict(list)
    for record in records:
        by_method[record.method].append(record)
    lines.append("=== method별 MAPE ===")
    for method in sorted(by_method):
        subset = by_method[method]
        lines.append(
            f"{method}: {len(subset)}일, MAPE {statistics.mean([r.error_pct for r in subset]):.1f}%"
        )
    lines.append("")

    worst = sorted(records, key=lambda item: item.error_pct, reverse=True)[:top]
    lines.append(f"=== 상위 오차 Top {top} ===")
    for record in worst:
        lines.append(
            f"{record.report_date} (target {record.target_date}) | "
            f"예측 {record.forecast:.1f} vs 실제 {record.actual:.1f} | "
            f"{record.error_pct:.1f}% {record.direction} | "
            f"{record.method} | {record.period_category} | {record.period_labels}"
        )
    lines.append("")

    top_period_share = sum(1 for record in worst if record.period_category != "normal") / len(worst) * 100
    lines.append(f"상위 {top}건 중 비정상(normal 외) 기간 비율: {top_period_share:.1f}%")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="전일 예측 오차 상세 분석")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "imc_dashboard.db",
    )
    parser.add_argument("--year", type=str, default="2026")
    parser.add_argument("--weekday-only", action="store_true")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--use-cache", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "forecast_error_analysis_2026.txt",
    )
    args = parser.parse_args()

    records = collect_errors(
        args.db,
        year=args.year,
        weekday_only=args.weekday_only,
        use_cache=args.use_cache,
    )
    report = format_report(records, args.top)
    print(report)
    args.output.write_text(report, encoding="utf-8")
    print(f"\n결과 저장: {args.output}")


if __name__ == "__main__":
    main()
