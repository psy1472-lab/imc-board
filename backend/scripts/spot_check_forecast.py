from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from application.briefing_service import BriefingService
from domain.volume_forecast import forecast_next_day_volume
from infrastructure.db.sqlite_repository import SqliteRepository

BASE = Path(__file__).resolve().parents[2]
DB = BASE / "data" / "imc_dashboard.db"


def main() -> None:
    repo = SqliteRepository(str(DB))
    svc = BriefingService(repo)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT rm.report_date, ds.total_volume
        FROM report_metadata rm
        JOIN daily_summary ds ON ds.report_date = rm.report_date
        ORDER BY rm.report_date DESC
        LIMIT 12
        """
    ).fetchall()

    from domain.day_type import resolve_day_type

    for row in rows:
        report_date = row["report_date"]
        day_type = resolve_day_type(date.fromisoformat(report_date))
        ctx = repo.get_volume_forecast_context(report_date)
        volume = repo.get_volume_analysis(report_date)
        benchmarks = volume["benchmarks"]
        weekday_trend = volume["trends"]["weekday"]

        old = forecast_next_day_volume(
            report_date,
            today_volume=volume["summary"]["totalVolume"],
            avg_7d_volume=benchmarks["avg7d"]["totalVolume"],
            avg_30d_volume=benchmarks["avg30d"]["totalVolume"],
            recent_7d_volumes=volume["trends"]["7d"]["totalVolume"],
            weekday_volumes=weekday_trend["totalVolume"],
            weekday_sample_counts=weekday_trend["sampleCounts"],
        )
        new = forecast_next_day_volume(
            report_date,
            today_volume=ctx["todayVolume"],
            avg_7d_volume=benchmarks["avg7d"]["totalVolume"],
            avg_30d_volume=benchmarks["avg30d"]["totalVolume"],
            recent_7d_volumes=volume["trends"]["7d"]["totalVolume"],
            weekday_volumes=weekday_trend["totalVolume"],
            weekday_sample_counts=weekday_trend["sampleCounts"],
            tomorrow_day_type=ctx["tomorrowDayType"],
            same_type_baseline=ctx["sameTypeBaseline"],
            same_type_avg_7d=ctx["sameTypeAvg7d"],
            same_type_avg_30d=ctx["sameTypeAvg30d"],
            same_type_recent_volumes=ctx["sameTypeRecent7d"],
            same_type_sample_count=ctx["sameTypeSampleCount"],
            today_type_avg_7d=ctx["todayTypeAvg7d"],
        )

        next_date = (date.fromisoformat(report_date) + timedelta(days=1)).isoformat()
        actual_row = conn.execute(
            "SELECT total_volume FROM daily_summary WHERE report_date = ?",
            (next_date,),
        ).fetchone()
        actual = actual_row["total_volume"] / 1000 if actual_row else None

        print(f"--- {report_date} ({day_type}) -> {ctx['tomorrowDayType']}")
        print(f"  mixed 7d avg: {benchmarks['avg7d']['totalVolume']}")
        print(f"  same-type baseline: {ctx['sameTypeBaseline']}")
        if old and new:
            print(
                f"  OLD forecast: {old.forecast_volume:.1f} | "
                f"NEW: {new.forecast_volume:.1f} | ACTUAL: {actual}"
            )
        briefing = svc.generate(report_date)
        for item in briefing.get("tomorrowOutlook", {}).get("items", []):
            if item["label"] in ("예상 물량", "전일 예측 검증"):
                print(f"  [{item['label']}] {item['text']}")


if __name__ == "__main__":
    main()
