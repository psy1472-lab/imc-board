from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from domain.day_type import resolve_day_type
from domain.operation_period import (
    compute_historical_no_parcel_avg,
    get_operation_periods_for_date,
    operation_period_labels,
)
from domain.transport_quota import quota_overage, quota_status
from domain.volume_forecast import forecast_target_note_for, resolve_forecast_target_date
from domain.entities import ParsedReport
from domain.hour_slots import HOUR_SLOTS, format_hour_label, normalize_hour_slot


class SqliteRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_schema(self) -> None:
        migrations_dir = Path(__file__).resolve().parents[4] / "supabase" / "migrations"
        with self._connect() as conn:
            for migration_name in ("001_initial_schema.sql", "002_operation_period.sql"):
                migration_path = migrations_dir / migration_name
                if migration_path.exists():
                    with open(migration_path, encoding="utf-8") as file:
                        conn.executescript(file.read())
            try:
                conn.execute("ALTER TABLE report_metadata ADD COLUMN day_type TEXT")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def get_health_status(self) -> dict:
        migrations = ["001_initial_schema.sql", "002_operation_period.sql"]
        with self._connect() as conn:
            report_count = conn.execute("SELECT COUNT(*) FROM report_metadata").fetchone()[0]
            latest = conn.execute(
                "SELECT MAX(report_date) FROM report_metadata"
            ).fetchone()[0]
        return {
            "database": "sqlite",
            "path": self.db_path,
            "migrations": migrations,
            "reportCount": int(report_count),
            "latestReportDate": latest,
        }

    def save_report(self, path: str, report: ParsedReport) -> None:
        report_date = report.report_date.isoformat()
        summary = report.daily_summary
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO report_metadata
                (report_date, center_name, report_format, day_type, file_path, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report_date,
                    report.center_name,
                    report.report_format,
                    report.day_type,
                    path,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO daily_summary
                (report_date, center_name, national_volume, total_volume, dispatch_volume,
                 arrival_volume, remaining_volume, productivity, ips_rate, last_operation_time,
                 communication_status, raw_values)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_date,
                    summary.center_name,
                    summary.national_volume,
                    summary.total_volume,
                    summary.dispatch_volume,
                    summary.arrival_volume,
                    summary.remaining_volume,
                    summary.productivity,
                    summary.ips_rate,
                    summary.last_operation_time.isoformat() if summary.last_operation_time else None,
                    summary.communication_status,
                    json.dumps(summary.raw_values, ensure_ascii=False),
                ),
            )

            conn.execute("DELETE FROM hourly_throughput WHERE report_date = ?", (report_date,))
            for item in report.hourly_throughput:
                conn.execute(
                    """
                    INSERT INTO hourly_throughput
                    (report_date, hour_slot, dispatch_volume, arrival_volume, total_volume)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        item.hour_slot,
                        item.dispatch_volume,
                        item.arrival_volume,
                        item.total_volume,
                    ),
                )

            conn.execute("DELETE FROM staffing WHERE report_date = ?", (report_date,))
            for item in report.staffing:
                conn.execute(
                    """
                    INSERT INTO staffing
                    (report_date, hour_slot, actual_staff, productivity, absence_rate)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        item.hour_slot,
                        item.actual_staff,
                        item.productivity,
                        item.absence_rate,
                    ),
                )

            if report.quota_exchange:
                q = report.quota_exchange
                conn.execute(
                    """
                    INSERT OR REPLACE INTO quota_exchange
                    (report_date, quarter_standard, quarter_actual, quarter_difference,
                     exchange_standard, exchange_actual, exchange_difference, exchange_remaining)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        q.quarter_standard,
                        q.quarter_actual,
                        q.quarter_difference,
                        q.exchange_standard,
                        q.exchange_actual,
                        q.exchange_difference,
                        q.exchange_remaining,
                    ),
                )

            conn.execute("DELETE FROM transport_office WHERE report_date = ?", (report_date,))
            for item in report.transport_offices:
                conn.execute(
                    """
                    INSERT INTO transport_office
                    (report_date, office_name, volume, vehicles_actual, vehicles_standard,
                     last_arrival_time, delay_minutes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        item.office_name,
                        item.volume,
                        item.vehicles_actual,
                        item.vehicles_standard,
                        item.last_arrival_time,
                        item.delay_minutes,
                        item.status,
                    ),
                )

            if report.sorting_machine:
                s = report.sorting_machine
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sorting_machine
                    (report_date, total_supply, total_sorted, sorting_rate, ips_rate, reject_rate,
                     shortcut_rate, avg_throughput, peak_throughput, unread_count, unread_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        s.total_supply,
                        s.total_sorted,
                        s.sorting_rate,
                        s.ips_rate,
                        s.reject_rate,
                        s.shortcut_rate,
                        s.avg_throughput,
                        s.peak_throughput,
                        s.unread_count,
                        s.unread_rate,
                    ),
                )

            conn.execute("DELETE FROM safety_summary WHERE report_date = ?", (report_date,))
            for item in report.safety_categories:
                conn.execute(
                    """
                    INSERT INTO safety_summary
                    (report_date, category, label, passed_items, total_items, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        item.category,
                        item.label,
                        item.passed_items,
                        item.total_items,
                        item.status,
                    ),
                )

            conn.execute("DELETE FROM safety_incident WHERE report_date = ?", (report_date,))
            for seq, item in enumerate(report.safety_incidents, start=1):
                conn.execute(
                    """
                    INSERT INTO safety_incident
                    (report_date, seq, department, victim_name, gender, occurrence_time, injury_type, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        seq,
                        item.department,
                        item.victim_name,
                        item.gender,
                        item.occurrence_time,
                        item.injury_type,
                        item.description,
                    ),
                )

            conn.execute("DELETE FROM anomaly WHERE report_date = ?", (report_date,))
            for item in report.anomalies:
                conn.execute(
                    """
                    INSERT INTO anomaly (report_date, category, severity, message, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (report_date, item.category, item.severity, item.message, item.source),
                )

            conn.execute("DELETE FROM validation_log WHERE report_date = ?", (report_date,))
            for item in report.validation_logs:
                conn.execute(
                    """
                    INSERT INTO validation_log (report_date, rule_name, status, details)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        report_date,
                        item["rule_name"],
                        item["status"],
                        json.dumps(item["details"], ensure_ascii=False),
                    ),
                )
            conn.commit()

        self._rebuild_comparisons(report.report_date)

    def _national_processing_rate(
        self, total_volume: int | float | None, national_volume: int | float | None
    ) -> float | None:
        if not total_volume or not national_volume:
            return None
        return round((total_volume / national_volume) * 100, 2)

    def _comparison_metrics(self) -> list[str]:
        return [
            "total_volume",
            "dispatch_volume",
            "arrival_volume",
            "national_volume",
            "productivity",
            "ips_rate",
        ]

    def _average_metric(self, rows: list[sqlite3.Row], metric: str) -> float | None:
        values = [row[metric] for row in rows if row[metric] is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def _build_comparison(
        self,
        current_value: float | int | None,
        compare_value: float | int | None,
    ) -> dict | None:
        if current_value is None or compare_value in (None, 0):
            return None
        difference = current_value - compare_value
        difference_percent = (difference / compare_value) * 100
        trend = "UP" if difference > 0 else "DOWN" if difference < 0 else "STABLE"
        return {
            "current_value": current_value,
            "compare_value": compare_value,
            "difference": difference,
            "difference_percent": difference_percent,
            "trend": trend,
        }

    def _load_comparisons(
        self, conn: sqlite3.Connection, report_date: str, compare_basis: str
    ) -> dict[str, dict]:
        current = conn.execute(
            "SELECT * FROM daily_summary WHERE report_date = ?",
            (report_date,),
        ).fetchone()
        if not current:
            return {}

        if compare_basis == "prev_day":
            stored = {
                row["metric_name"]: row
                for row in conn.execute(
                    """
                    SELECT * FROM kpi_comparison
                    WHERE report_date = ? AND compare_basis = 'prev_day'
                    """,
                    (report_date,),
                ).fetchall()
            }
            if stored:
                return stored

            prev = conn.execute(
                """
                SELECT * FROM daily_summary
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 1
                """,
                (report_date,),
            ).fetchone()
            if not prev:
                return {}
            return {
                metric: self._build_comparison(current[metric], prev[metric])
                for metric in self._comparison_metrics()
                if self._build_comparison(current[metric], prev[metric])
            }

        if compare_basis in {"7d_avg", "30d_avg"}:
            limit = 7 if compare_basis == "7d_avg" else 30
            rows = conn.execute(
                """
                SELECT * FROM daily_summary
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT ?
                """,
                (report_date, limit),
            ).fetchall()
            if not rows:
                return {}
            comparisons: dict[str, dict] = {}
            for metric in self._comparison_metrics():
                compare_value = self._average_metric(rows, metric)
                built = self._build_comparison(current[metric], compare_value)
                if built:
                    comparisons[metric] = built
            return comparisons

        if compare_basis == "same_weekday":
            rows = conn.execute(
                """
                SELECT * FROM daily_summary
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            report_weekday = date.fromisoformat(report_date).weekday()
            same_weekday_rows = [
                row
                for row in rows
                if date.fromisoformat(row["report_date"]).weekday() == report_weekday
            ]
            if not same_weekday_rows:
                return {}
            comparisons = {}
            for metric in self._comparison_metrics():
                compare_value = self._average_metric(same_weekday_rows, metric)
                built = self._build_comparison(current[metric], compare_value)
                if built:
                    comparisons[metric] = built
            return comparisons

        return {}

    def _to_thousand(self, value: int | float | None) -> float | None:
        if value is None:
            return None
        return round(value / 1000, 1)

    def _volume_processing_rates(
        self,
        total_volume: int | float | None,
        dispatch_volume: int | float | None,
        arrival_volume: int | float | None,
        national_volume: int | float | None,
    ) -> tuple[float | None, float | None, float | None]:
        if not national_volume:
            return None, None, None
        return (
            round((total_volume / national_volume) * 100, 2) if total_volume is not None else None,
            round((dispatch_volume / national_volume) * 100, 2) if dispatch_volume is not None else None,
            round((arrival_volume / national_volume) * 100, 2) if arrival_volume is not None else None,
        )

    def _serialize_trend_rows(self, rows: list[sqlite3.Row]) -> dict:
        reversed_rows = list(reversed(rows))
        total_rates: list[float | None] = []
        dispatch_rates: list[float | None] = []
        arrival_rates: list[float | None] = []
        for row in reversed_rows:
            total_rate, dispatch_rate, arrival_rate = self._volume_processing_rates(
                row["total_volume"],
                row["dispatch_volume"],
                row["arrival_volume"],
                row["national_volume"],
            )
            total_rates.append(total_rate)
            dispatch_rates.append(dispatch_rate)
            arrival_rates.append(arrival_rate)

        return {
            "reportDates": [row["report_date"] for row in reversed_rows],
            "dates": [row["report_date"][5:] for row in reversed_rows],
            "totalVolume": [self._to_thousand(row["total_volume"]) for row in reversed_rows],
            "dispatchVolume": [self._to_thousand(row["dispatch_volume"]) for row in reversed_rows],
            "arrivalVolume": [self._to_thousand(row["arrival_volume"]) for row in reversed_rows],
            "nationalVolume": [self._to_thousand(row["national_volume"]) for row in reversed_rows],
            "totalProcessingRate": total_rates,
            "dispatchProcessingRate": dispatch_rates,
            "arrivalProcessingRate": arrival_rates,
        }

    def _serialize_weekday_average(self, rows: list[sqlite3.Row]) -> dict:
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        buckets: dict[int, list[sqlite3.Row]] = {index: [] for index in range(7)}
        for row in rows:
            weekday = date.fromisoformat(row["report_date"]).weekday()
            buckets[weekday].append(row)

        def avg_metric(weekday: int, metric: str) -> float | None:
            return self._to_thousand(self._average_metric(buckets[weekday], metric))

        def avg_rate(weekday: int, metric: str) -> float | None:
            avg_value = self._average_metric(buckets[weekday], metric)
            avg_national = self._average_metric(buckets[weekday], "national_volume")
            if not avg_value or not avg_national:
                return None
            return round((avg_value / avg_national) * 100, 2)

        return {
            "mode": "weekday",
            "labels": weekday_labels,
            "reportDates": weekday_labels,
            "dates": weekday_labels,
            "totalVolume": [avg_metric(index, "total_volume") for index in range(7)],
            "dispatchVolume": [avg_metric(index, "dispatch_volume") for index in range(7)],
            "arrivalVolume": [avg_metric(index, "arrival_volume") for index in range(7)],
            "nationalVolume": [avg_metric(index, "national_volume") for index in range(7)],
            "totalProcessingRate": [avg_rate(index, "total_volume") for index in range(7)],
            "dispatchProcessingRate": [avg_rate(index, "dispatch_volume") for index in range(7)],
            "arrivalProcessingRate": [avg_rate(index, "arrival_volume") for index in range(7)],
            "sampleCounts": [len(buckets[index]) for index in range(7)],
        }

    def _sum_metric(self, rows: list[sqlite3.Row], metric: str) -> int | None:
        values = [row[metric] for row in rows if row[metric] is not None]
        if not values:
            return None
        return int(sum(values))

    def _avg_daily_thousand(self, total_raw: int | None, day_count: int) -> float | None:
        if total_raw is None or day_count <= 0:
            return None
        return round(total_raw / 1000 / day_count, 1)

    def _build_year_to_date_summary(self, rows: list[sqlite3.Row], year: int, report_date: str) -> dict:
        national_raw = self._sum_metric(rows, "national_volume")
        total_raw = self._sum_metric(rows, "total_volume")
        dispatch_raw = self._sum_metric(rows, "dispatch_volume")
        arrival_raw = self._sum_metric(rows, "arrival_volume")
        day_count = len(rows)
        return {
            "year": year,
            "startDate": f"{year}-01-01",
            "endDate": report_date,
            "dayCount": day_count,
            "nationalVolume": self._to_thousand(national_raw),
            "totalVolume": self._to_thousand(total_raw),
            "dispatchVolume": self._to_thousand(dispatch_raw),
            "arrivalVolume": self._to_thousand(arrival_raw),
            "avgNationalVolume": self._avg_daily_thousand(national_raw, day_count),
            "avgTotalVolume": self._avg_daily_thousand(total_raw, day_count),
            "avgDispatchVolume": self._avg_daily_thousand(dispatch_raw, day_count),
            "avgArrivalVolume": self._avg_daily_thousand(arrival_raw, day_count),
            "processingRate": self._national_processing_rate(total_raw, national_raw),
        }

    def _serialize_monthly_volume_trend(self, rows: list[sqlite3.Row], year: int) -> dict:
        month_buckets: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            month_key = row["report_date"][:7]
            month_buckets.setdefault(month_key, []).append(row)

        month_keys = sorted(month_buckets.keys())
        labels = [f"{int(month_key.split('-')[1])}월" for month_key in month_keys]
        total_volumes: list[float | None] = []
        dispatch_volumes: list[float | None] = []
        arrival_volumes: list[float | None] = []
        national_volumes: list[float | None] = []
        total_rates: list[float | None] = []
        sample_counts: list[int] = []

        for month_key in month_keys:
            bucket = month_buckets[month_key]
            national_raw = self._sum_metric(bucket, "national_volume")
            total_raw = self._sum_metric(bucket, "total_volume")
            dispatch_raw = self._sum_metric(bucket, "dispatch_volume")
            arrival_raw = self._sum_metric(bucket, "arrival_volume")
            total_volumes.append(self._to_thousand(total_raw))
            dispatch_volumes.append(self._to_thousand(dispatch_raw))
            arrival_volumes.append(self._to_thousand(arrival_raw))
            national_volumes.append(self._to_thousand(national_raw))
            total_rates.append(self._national_processing_rate(total_raw, national_raw))
            sample_counts.append(len(bucket))

        return {
            "mode": "monthly",
            "year": year,
            "labels": labels,
            "months": month_keys,
            "reportDates": month_keys,
            "dates": labels,
            "totalVolume": total_volumes,
            "dispatchVolume": dispatch_volumes,
            "arrivalVolume": arrival_volumes,
            "nationalVolume": national_volumes,
            "totalProcessingRate": total_rates,
            "sampleCounts": sample_counts,
        }

    def get_volume_analysis(self, report_date: str) -> dict:
        with self._connect() as conn:
            summary = conn.execute(
                "SELECT * FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            metadata = conn.execute(
                "SELECT report_format, day_type FROM report_metadata WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            if not summary:
                return {}

            trend_rows = conn.execute(
                """
                SELECT report_date, total_volume, dispatch_volume, arrival_volume, national_volume,
                       remaining_volume
                FROM daily_summary
                WHERE report_date <= ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            prev_rows = conn.execute(
                """
                SELECT * FROM daily_summary
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            report_year = date.fromisoformat(report_date).year
            year_rows = conn.execute(
                """
                SELECT report_date, total_volume, dispatch_volume, arrival_volume, national_volume
                FROM daily_summary
                WHERE report_date >= ? AND report_date <= ?
                ORDER BY report_date
                """,
                (f"{report_year}-01-01", report_date),
            ).fetchall()
            prior_year = report_year - 1
            prior_end_date = f"{prior_year}-{report_date[5:]}"
            prior_year_rows = conn.execute(
                """
                SELECT report_date, total_volume, dispatch_volume, arrival_volume, national_volume
                FROM daily_summary
                WHERE report_date >= ? AND report_date <= ?
                ORDER BY report_date
                """,
                (f"{prior_year}-01-01", prior_end_date),
            ).fetchall()

        trend_7d = trend_rows[:7]
        trend_30d = trend_rows
        trend_30d_series = self._serialize_trend_rows(trend_30d)
        avg7 = prev_rows[:7]
        avg30 = prev_rows[:30]
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        report_weekday = date.fromisoformat(report_date).weekday()
        same_weekday_rows = [
            row
            for row in prev_rows
            if date.fromisoformat(row["report_date"]).weekday() == report_weekday
        ]

        def benchmark(key: str) -> float | None:
            if key == "avg7d":
                return self._average_metric(avg7, "total_volume")
            if key == "avg30d":
                return self._average_metric(avg30, "total_volume")
            if key == "prev_day" and prev_rows:
                return prev_rows[0]["total_volume"]
            return None

        processing_rate = self._national_processing_rate(
            summary["total_volume"], summary["national_volume"]
        )

        return {
            "meta": {
                "reportDate": report_date,
                "centerName": summary["center_name"],
                "reportFormat": metadata["report_format"] if metadata else None,
                "dayType": metadata["day_type"] if metadata else None,
            },
            "summary": {
                "nationalVolume": self._to_thousand(summary["national_volume"]),
                "totalVolume": self._to_thousand(summary["total_volume"]),
                "dispatchVolume": self._to_thousand(summary["dispatch_volume"]),
                "arrivalVolume": self._to_thousand(summary["arrival_volume"]),
                "remainingVolume": self._to_thousand(summary["remaining_volume"]),
                "processingRate": processing_rate,
            },
            "benchmarks": {
                "prevDay": {
                    "totalVolume": self._to_thousand(benchmark("prev_day")),
                    "dispatchVolume": self._to_thousand(prev_rows[0]["dispatch_volume"]) if prev_rows else None,
                    "arrivalVolume": self._to_thousand(prev_rows[0]["arrival_volume"]) if prev_rows else None,
                },
                "avg7d": {
                    "totalVolume": self._to_thousand(self._average_metric(avg7, "total_volume")),
                    "dispatchVolume": self._to_thousand(self._average_metric(avg7, "dispatch_volume")),
                    "arrivalVolume": self._to_thousand(self._average_metric(avg7, "arrival_volume")),
                },
                "avg30d": {
                    "totalVolume": self._to_thousand(self._average_metric(avg30, "total_volume")),
                    "dispatchVolume": self._to_thousand(self._average_metric(avg30, "dispatch_volume")),
                    "arrivalVolume": self._to_thousand(self._average_metric(avg30, "arrival_volume")),
                },
                "sameWeekday": {
                    "weekdayLabel": weekday_labels[report_weekday],
                    "sampleCount": len(same_weekday_rows),
                    "totalVolume": self._to_thousand(self._average_metric(same_weekday_rows, "total_volume")),
                    "dispatchVolume": self._to_thousand(self._average_metric(same_weekday_rows, "dispatch_volume")),
                    "arrivalVolume": self._to_thousand(self._average_metric(same_weekday_rows, "arrival_volume")),
                },
            },
            "trends": {
                "7d": self._serialize_trend_rows(trend_7d),
                "30d": trend_30d_series,
                "weekday": self._serialize_weekday_average(trend_30d),
            },
            "yearToDate": self._build_year_to_date_summary(year_rows, report_year, report_date),
            "priorYearToDate": self._build_year_to_date_summary(prior_year_rows, prior_year, prior_end_date)
            if prior_year_rows
            else None,
            "monthlyTrend": self._serialize_monthly_volume_trend(year_rows, report_year),
            "dailyTrend": trend_30d_series,
        }

    def _staffing_aggregate_map(
        self, conn: sqlite3.Connection, report_dates: list[str]
    ) -> dict[str, dict[str, float | int | None]]:
        if not report_dates:
            return {}
        placeholders = ",".join("?" * len(report_dates))
        rows = conn.execute(
            f"""
            SELECT report_date,
                   AVG(actual_staff) AS avg_staff,
                   MAX(actual_staff) AS peak_staff
            FROM staffing
            WHERE report_date IN ({placeholders}) AND actual_staff IS NOT NULL
            GROUP BY report_date
            """,
            report_dates,
        ).fetchall()
        return {
            row["report_date"]: {
                "avgStaff": round(row["avg_staff"], 1),
                "peakStaff": row["peak_staff"],
            }
            for row in rows
        }

    def _serialize_staffing_trend_rows(
        self, rows: list[sqlite3.Row], staffing_map: dict[str, dict[str, float | int | None]]
    ) -> dict:
        reversed_rows = list(reversed(rows))
        return {
            "reportDates": [row["report_date"] for row in reversed_rows],
            "dates": [row["report_date"][5:] for row in reversed_rows],
            "productivity": [row["productivity"] for row in reversed_rows],
            "volume": [self._to_thousand(row["total_volume"]) for row in reversed_rows],
            "avgStaff": [
                staffing_map.get(row["report_date"], {}).get("avgStaff") for row in reversed_rows
            ],
            "peakStaff": [
                staffing_map.get(row["report_date"], {}).get("peakStaff") for row in reversed_rows
            ],
        }

    def _serialize_staffing_weekday_average(
        self, rows: list[sqlite3.Row], staffing_map: dict[str, dict[str, float | int | None]]
    ) -> dict:
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        buckets: dict[int, list[sqlite3.Row]] = {index: [] for index in range(7)}
        for row in rows:
            weekday = date.fromisoformat(row["report_date"]).weekday()
            buckets[weekday].append(row)

        def avg_productivity(weekday: int) -> float | None:
            values = [row["productivity"] for row in buckets[weekday] if row["productivity"] is not None]
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        def avg_staff_metric(weekday: int, metric: str) -> float | None:
            values = [
                staffing_map.get(row["report_date"], {}).get(metric)
                for row in buckets[weekday]
                if staffing_map.get(row["report_date"], {}).get(metric) is not None
            ]
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        return {
            "mode": "weekday",
            "labels": weekday_labels,
            "reportDates": weekday_labels,
            "dates": weekday_labels,
            "productivity": [avg_productivity(index) for index in range(7)],
            "volume": [
                self._to_thousand(self._average_metric(buckets[index], "total_volume"))
                for index in range(7)
            ],
            "avgStaff": [avg_staff_metric(index, "avgStaff") for index in range(7)],
            "peakStaff": [avg_staff_metric(index, "peakStaff") for index in range(7)],
            "sampleCounts": [len(buckets[index]) for index in range(7)],
        }

    def _staffing_benchmark(
        self,
        staffing_map: dict[str, dict[str, float | int | None]],
        summary_rows: list[sqlite3.Row],
    ) -> dict:
        if not summary_rows:
            return {"productivity": None, "avgStaff": None, "peakStaff": None}
        productivity = self._average_metric(summary_rows, "productivity")
        avg_staff_values = [
            staffing_map.get(row["report_date"], {}).get("avgStaff")
            for row in summary_rows
            if staffing_map.get(row["report_date"], {}).get("avgStaff") is not None
        ]
        peak_staff_values = [
            staffing_map.get(row["report_date"], {}).get("peakStaff")
            for row in summary_rows
            if staffing_map.get(row["report_date"], {}).get("peakStaff") is not None
        ]
        return {
            "productivity": round(productivity, 1) if productivity is not None else None,
            "avgStaff": round(sum(avg_staff_values) / len(avg_staff_values), 1) if avg_staff_values else None,
            "peakStaff": round(sum(peak_staff_values) / len(peak_staff_values), 1) if peak_staff_values else None,
        }

    def get_staffing_analysis(self, report_date: str) -> dict:
        with self._connect() as conn:
            summary = conn.execute(
                "SELECT * FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            if not summary:
                return {}

            hourly = conn.execute(
                "SELECT * FROM hourly_throughput WHERE report_date = ?",
                (report_date,),
            ).fetchall()
            staffing = conn.execute(
                "SELECT * FROM staffing WHERE report_date = ?",
                (report_date,),
            ).fetchall()
            trend_rows = conn.execute(
                """
                SELECT report_date, total_volume, productivity
                FROM daily_summary
                WHERE report_date <= ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            prev_rows = conn.execute(
                """
                SELECT report_date, total_volume, productivity
                FROM daily_summary
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()

            trend_dates = [row["report_date"] for row in trend_rows]
            staffing_map = self._staffing_aggregate_map(conn, trend_dates)

        ordered_hourly = self._order_hourly_rows(hourly)
        ordered_staffing = self._order_hourly_rows(staffing)
        peak_hour_row = self._peak_hourly_row(hourly)
        staff_values = [row["actual_staff"] for row in staffing if row["actual_staff"] is not None]
        avg_staff = round(sum(staff_values) / len(staff_values), 1) if staff_values else None
        peak_staff_row = max(staffing, key=lambda row: row["actual_staff"] or 0, default=None)

        trend_7d = trend_rows[:7]
        trend_30d = trend_rows
        trend_30d_series = self._serialize_staffing_trend_rows(trend_30d, staffing_map)
        avg7 = prev_rows[:7]
        avg30 = prev_rows[:30]
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        report_weekday = date.fromisoformat(report_date).weekday()
        same_weekday_rows = [
            row
            for row in prev_rows
            if date.fromisoformat(row["report_date"]).weekday() == report_weekday
        ]
        prev_day_rows = prev_rows[:1]

        return {
            "meta": {
                "reportDate": report_date,
                "centerName": summary["center_name"],
            },
            "summary": {
                "productivity": summary["productivity"],
                "avgStaff": avg_staff,
                "peakStaff": peak_staff_row["actual_staff"] if peak_staff_row else None,
                "peakHour": format_hour_label(str(peak_hour_row["hour_slot"])) if peak_hour_row else None,
                "peakHourVolume": self._to_thousand(peak_hour_row["total_volume"]) if peak_hour_row else None,
                "totalVolume": self._to_thousand(summary["total_volume"]),
            },
            "hourly": {
                "slots": list(HOUR_SLOTS),
                "labels": [format_hour_label(slot) for slot in HOUR_SLOTS],
                "volume": [
                    self._to_thousand(ordered_hourly[slot]["total_volume"]) if ordered_hourly[slot] else None
                    for slot in HOUR_SLOTS
                ],
                "staff": [
                    ordered_staffing[slot]["actual_staff"] if ordered_staffing[slot] else None
                    for slot in HOUR_SLOTS
                ],
                "productivity": [
                    ordered_staffing[slot]["productivity"] if ordered_staffing[slot] else None
                    for slot in HOUR_SLOTS
                ],
            },
            "benchmarks": {
                "prevDay": self._staffing_benchmark(staffing_map, prev_day_rows),
                "avg7d": self._staffing_benchmark(staffing_map, avg7),
                "avg30d": self._staffing_benchmark(staffing_map, avg30),
                "sameWeekday": {
                    **self._staffing_benchmark(staffing_map, same_weekday_rows),
                    "weekdayLabel": weekday_labels[report_weekday],
                    "sampleCount": len(same_weekday_rows),
                },
            },
            "trends": {
                "7d": self._serialize_staffing_trend_rows(trend_7d, staffing_map),
                "30d": trend_30d_series,
                "weekday": self._serialize_staffing_weekday_average(trend_30d, staffing_map),
            },
            "dailyTrend": trend_30d_series,
        }

    def _compliance_rate(self, actual: int | float | None, standard: int | float | None) -> float | None:
        if actual is None or standard in (None, 0):
            return None
        return round((actual / standard) * 100, 1)

    def _serialize_office_row(self, row: sqlite3.Row) -> dict:
        overage = quota_overage(row["vehicles_actual"], row["vehicles_standard"])
        status = quota_status(row["vehicles_actual"], row["vehicles_standard"])
        return {
            "office": row["office_name"],
            "volume": row["volume"],
            "vehiclesActual": row["vehicles_actual"],
            "vehiclesQuota": row["vehicles_standard"],
            "difference": overage,
            "arrivalTime": row["last_arrival_time"],
            "delayMinutes": overage if overage and overage > 0 else None,
            "status": status,
        }

    def _office_is_quota_overage(self, row: sqlite3.Row) -> bool:
        overage = quota_overage(row["vehicles_actual"], row["vehicles_standard"])
        return overage is not None and overage > 0

    def _transport_summary(self, quota: sqlite3.Row | None, offices: list[sqlite3.Row]) -> dict:
        overage_count = sum(1 for row in offices if self._office_is_quota_overage(row))
        delayed_count = sum(
            1
            for row in offices
            if self._office_is_quota_overage(row)
        )
        total_volume = sum(row["volume"] or 0 for row in offices)
        return {
            "quarterActual": quota["quarter_actual"] if quota else None,
            "quarterStandard": quota["quarter_standard"] if quota else None,
            "quarterComplianceRate": self._compliance_rate(
                quota["quarter_actual"] if quota else None,
                quota["quarter_standard"] if quota else None,
            ),
            "exchangeActual": quota["exchange_actual"] if quota else None,
            "exchangeStandard": quota["exchange_standard"] if quota else None,
            "exchangeComplianceRate": self._compliance_rate(
                quota["exchange_actual"] if quota else None,
                quota["exchange_standard"] if quota else None,
            ),
            "exchangeRemaining": quota["exchange_remaining"] if quota else None,
            "overageOfficeCount": overage_count,
            "delayedOfficeCount": delayed_count,
            "totalOfficeVolume": total_volume if offices else None,
            "officeCount": len(offices),
        }

    def _overage_count_map(
        self, conn: sqlite3.Connection, report_dates: list[str]
    ) -> dict[str, int]:
        if not report_dates:
            return {}
        placeholders = ",".join("?" * len(report_dates))
        rows = conn.execute(
            f"""
            SELECT report_date, COUNT(*) AS overage_count
            FROM transport_office
            WHERE report_date IN ({placeholders})
              AND vehicles_actual IS NOT NULL
              AND vehicles_standard IS NOT NULL
              AND vehicles_actual > vehicles_standard
            GROUP BY report_date
            """,
            report_dates,
        ).fetchall()
        return {row["report_date"]: row["overage_count"] for row in rows}

    def _transport_metrics_for_dates(
        self, conn: sqlite3.Connection, report_dates: list[str]
    ) -> dict[str, dict]:
        if not report_dates:
            return {}
        placeholders = ",".join("?" * len(report_dates))
        quota_rows = conn.execute(
            f"SELECT * FROM quota_exchange WHERE report_date IN ({placeholders})",
            report_dates,
        ).fetchall()
        office_rows = conn.execute(
            f"SELECT * FROM transport_office WHERE report_date IN ({placeholders})",
            report_dates,
        ).fetchall()
        quota_by_date = {row["report_date"]: row for row in quota_rows}
        offices_by_date: dict[str, list[sqlite3.Row]] = {date_key: [] for date_key in report_dates}
        for row in office_rows:
            offices_by_date.setdefault(row["report_date"], []).append(row)
        return {
            date_key: self._transport_summary(quota_by_date.get(date_key), offices_by_date.get(date_key, []))
            for date_key in report_dates
        }

    def _transport_benchmark(self, metrics_by_date: dict[str, dict], report_dates: list[str]) -> dict:
        metrics = [metrics_by_date[date_key] for date_key in report_dates if date_key in metrics_by_date]
        if not metrics:
            return {
                "quarterComplianceRate": None,
                "exchangeComplianceRate": None,
                "overageOfficeCount": None,
            }

        def avg_metric(field: str) -> float | None:
            values = [metric[field] for metric in metrics if metric.get(field) is not None]
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        return {
            "quarterComplianceRate": avg_metric("quarterComplianceRate"),
            "exchangeComplianceRate": avg_metric("exchangeComplianceRate"),
            "overageOfficeCount": avg_metric("overageOfficeCount"),
        }

    def _serialize_transport_trend_rows(
        self, rows: list[sqlite3.Row], overage_map: dict[str, int]
    ) -> dict:
        reversed_rows = list(reversed(rows))
        return {
            "reportDates": [row["report_date"] for row in reversed_rows],
            "dates": [row["report_date"][5:] for row in reversed_rows],
            "quarterComplianceRate": [
                self._compliance_rate(row["quarter_actual"], row["quarter_standard"])
                for row in reversed_rows
            ],
            "exchangeComplianceRate": [
                self._compliance_rate(row["exchange_actual"], row["exchange_standard"])
                for row in reversed_rows
            ],
            "overageOfficeCount": [overage_map.get(row["report_date"], 0) for row in reversed_rows],
        }

    def _serialize_transport_weekday_average(
        self, rows: list[sqlite3.Row], overage_map: dict[str, int]
    ) -> dict:
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        buckets: dict[int, list[sqlite3.Row]] = {index: [] for index in range(7)}
        for row in rows:
            weekday = date.fromisoformat(row["report_date"]).weekday()
            buckets[weekday].append(row)

        def avg_rate(weekday: int, actual_field: str, standard_field: str) -> float | None:
            rates = [
                self._compliance_rate(item[actual_field], item[standard_field])
                for item in buckets[weekday]
                if item[actual_field] is not None and item[standard_field]
            ]
            rates = [rate for rate in rates if rate is not None]
            if not rates:
                return None
            return round(sum(rates) / len(rates), 1)

        def avg_overage(weekday: int) -> float | None:
            values = [overage_map.get(item["report_date"], 0) for item in buckets[weekday]]
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        return {
            "mode": "weekday",
            "labels": weekday_labels,
            "reportDates": weekday_labels,
            "dates": weekday_labels,
            "quarterComplianceRate": [
                avg_rate(index, "quarter_actual", "quarter_standard") for index in range(7)
            ],
            "exchangeComplianceRate": [
                avg_rate(index, "exchange_actual", "exchange_standard") for index in range(7)
            ],
            "overageOfficeCount": [avg_overage(index) for index in range(7)],
            "sampleCounts": [len(buckets[index]) for index in range(7)],
        }

    def get_transport_analysis(self, report_date: str) -> dict:
        with self._connect() as conn:
            summary_exists = conn.execute(
                "SELECT 1 FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            if not summary_exists:
                return {}

            quota = conn.execute(
                "SELECT * FROM quota_exchange WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            offices = conn.execute(
                "SELECT * FROM transport_office WHERE report_date = ? ORDER BY office_name",
                (report_date,),
            ).fetchall()
            trend_rows = conn.execute(
                """
                SELECT report_date, quarter_actual, quarter_standard, exchange_actual, exchange_standard,
                       exchange_remaining
                FROM quota_exchange
                WHERE report_date <= ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            prev_rows = conn.execute(
                """
                SELECT report_date, quarter_actual, quarter_standard, exchange_actual, exchange_standard,
                       exchange_remaining
                FROM quota_exchange
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            center = conn.execute(
                "SELECT center_name FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()

        trend_dates = [row["report_date"] for row in trend_rows]
        benchmark_dates = [row["report_date"] for row in prev_rows]
        with self._connect() as conn:
            overage_map = self._overage_count_map(conn, trend_dates + benchmark_dates)
            metrics_by_date = self._transport_metrics_for_dates(conn, benchmark_dates + [report_date])

        trend_7d = trend_rows[:7]
        trend_30d = trend_rows
        trend_30d_series = self._serialize_transport_trend_rows(trend_30d, overage_map)
        avg7 = prev_rows[:7]
        avg30 = prev_rows[:30]
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        report_weekday = date.fromisoformat(report_date).weekday()
        same_weekday_rows = [
            row
            for row in prev_rows
            if date.fromisoformat(row["report_date"]).weekday() == report_weekday
        ]
        prev_day_rows = prev_rows[:1]
        current_summary = self._transport_summary(quota, offices)
        serialized_offices = [self._serialize_office_row(row) for row in offices]
        quota_overages = [office for office in serialized_offices if office["status"] == "WARNING"]

        return {
            "meta": {
                "reportDate": report_date,
                "centerName": center["center_name"] if center else None,
            },
            "summary": current_summary,
            "offices": serialized_offices,
            "quotaOverages": quota_overages,
            "benchmarks": {
                "prevDay": self._transport_benchmark(
                    metrics_by_date, [row["report_date"] for row in prev_day_rows]
                ),
                "avg7d": self._transport_benchmark(metrics_by_date, [row["report_date"] for row in avg7]),
                "avg30d": self._transport_benchmark(metrics_by_date, [row["report_date"] for row in avg30]),
                "sameWeekday": {
                    **self._transport_benchmark(
                        metrics_by_date, [row["report_date"] for row in same_weekday_rows]
                    ),
                    "weekdayLabel": weekday_labels[report_weekday],
                    "sampleCount": len(same_weekday_rows),
                },
            },
            "trends": {
                "7d": self._serialize_transport_trend_rows(trend_7d, overage_map),
                "30d": trend_30d_series,
                "weekday": self._serialize_transport_weekday_average(trend_30d, overage_map),
            },
            "dailyTrend": trend_30d_series,
        }

    def _equipment_summary(self, row: sqlite3.Row | None) -> dict:
        if not row:
            return {
                "totalSupply": None,
                "totalSorted": None,
                "sortingRate": None,
                "ipsRate": None,
                "rejectRate": None,
                "shortcutRate": None,
                "avgThroughput": None,
                "peakThroughput": None,
                "unreadCount": None,
                "unreadRate": None,
                "ipsTarget": 97.0,
            }
        return {
            "totalSupply": row["total_supply"],
            "totalSorted": row["total_sorted"],
            "sortingRate": row["sorting_rate"],
            "ipsRate": row["ips_rate"],
            "rejectRate": row["reject_rate"],
            "shortcutRate": row["shortcut_rate"],
            "avgThroughput": row["avg_throughput"],
            "peakThroughput": row["peak_throughput"],
            "unreadCount": row["unread_count"],
            "unreadRate": row["unread_rate"],
            "ipsTarget": 97.0,
        }

    def _equipment_benchmark(self, rows: list[sqlite3.Row]) -> dict:
        if not rows:
            return {
                "sortingRate": None,
                "ipsRate": None,
                "rejectRate": None,
                "unreadRate": None,
            }

        def avg_field(field: str) -> float | None:
            values = [row[field] for row in rows if row[field] is not None]
            if not values:
                return None
            return round(sum(values) / len(values), 2)

        return {
            "sortingRate": avg_field("sorting_rate"),
            "ipsRate": avg_field("ips_rate"),
            "rejectRate": avg_field("reject_rate"),
            "unreadRate": avg_field("unread_rate"),
        }

    def _serialize_equipment_trend_rows(self, rows: list[sqlite3.Row]) -> dict:
        reversed_rows = list(reversed(rows))
        return {
            "reportDates": [row["report_date"] for row in reversed_rows],
            "dates": [row["report_date"][5:] for row in reversed_rows],
            "sortingRate": [row["sorting_rate"] for row in reversed_rows],
            "ipsRate": [row["ips_rate"] for row in reversed_rows],
            "rejectRate": [row["reject_rate"] for row in reversed_rows],
            "unreadRate": [row["unread_rate"] for row in reversed_rows],
            "avgThroughput": [row["avg_throughput"] for row in reversed_rows],
            "peakThroughput": [row["peak_throughput"] for row in reversed_rows],
        }

    def _serialize_equipment_weekday_average(self, rows: list[sqlite3.Row]) -> dict:
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        buckets: dict[int, list[sqlite3.Row]] = {index: [] for index in range(7)}
        for row in rows:
            weekday = date.fromisoformat(row["report_date"]).weekday()
            buckets[weekday].append(row)

        def avg_field(weekday: int, field: str) -> float | None:
            values = [item[field] for item in buckets[weekday] if item[field] is not None]
            if not values:
                return None
            return round(sum(values) / len(values), 2)

        return {
            "mode": "weekday",
            "labels": weekday_labels,
            "reportDates": weekday_labels,
            "dates": weekday_labels,
            "sortingRate": [avg_field(index, "sorting_rate") for index in range(7)],
            "ipsRate": [avg_field(index, "ips_rate") for index in range(7)],
            "rejectRate": [avg_field(index, "reject_rate") for index in range(7)],
            "unreadRate": [avg_field(index, "unread_rate") for index in range(7)],
            "avgThroughput": [avg_field(index, "avg_throughput") for index in range(7)],
            "peakThroughput": [avg_field(index, "peak_throughput") for index in range(7)],
            "sampleCounts": [len(buckets[index]) for index in range(7)],
        }

    def get_equipment_analysis(self, report_date: str) -> dict:
        with self._connect() as conn:
            summary_exists = conn.execute(
                "SELECT 1 FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            if not summary_exists:
                return {}

            sorting = conn.execute(
                "SELECT * FROM sorting_machine WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            center = conn.execute(
                "SELECT center_name FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            trend_rows = conn.execute(
                """
                SELECT report_date, total_supply, total_sorted, sorting_rate, ips_rate, reject_rate,
                       shortcut_rate, avg_throughput, peak_throughput, unread_count, unread_rate
                FROM sorting_machine
                WHERE report_date <= ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            prev_rows = conn.execute(
                """
                SELECT report_date, total_supply, total_sorted, sorting_rate, ips_rate, reject_rate,
                       shortcut_rate, avg_throughput, peak_throughput, unread_count, unread_rate
                FROM sorting_machine
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()

        trend_7d = trend_rows[:7]
        trend_30d = trend_rows
        trend_30d_series = self._serialize_equipment_trend_rows(trend_30d)
        avg7 = prev_rows[:7]
        avg30 = prev_rows[:30]
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        report_weekday = date.fromisoformat(report_date).weekday()
        same_weekday_rows = [
            row
            for row in prev_rows
            if date.fromisoformat(row["report_date"]).weekday() == report_weekday
        ]
        prev_day_rows = prev_rows[:1]
        current_summary = self._equipment_summary(sorting)

        return {
            "meta": {
                "reportDate": report_date,
                "centerName": center["center_name"] if center else None,
            },
            "summary": current_summary,
            "benchmarks": {
                "prevDay": self._equipment_benchmark(prev_day_rows),
                "avg7d": self._equipment_benchmark(avg7),
                "avg30d": self._equipment_benchmark(avg30),
                "sameWeekday": {
                    **self._equipment_benchmark(same_weekday_rows),
                    "weekdayLabel": weekday_labels[report_weekday],
                    "sampleCount": len(same_weekday_rows),
                },
            },
            "trends": {
                "7d": self._serialize_equipment_trend_rows(trend_7d),
                "30d": trend_30d_series,
                "weekday": self._serialize_equipment_weekday_average(trend_30d),
            },
            "dailyTrend": trend_30d_series,
        }

    _ANOMALY_CATEGORY_LABELS = {
        "volume": "물량",
        "transport": "운송",
        "equipment": "설비",
        "safety": "안전",
        "staffing": "인력",
    }

    def _safety_pass_rate(self, rows: list[sqlite3.Row]) -> float | None:
        if not rows:
            return None
        passed = sum(row["passed_items"] or 0 for row in rows)
        total = sum(row["total_items"] or 0 for row in rows)
        if total == 0:
            return None
        return round((passed / total) * 100, 1)

    def _serialize_anomaly_row(self, row: sqlite3.Row) -> dict:
        category = row["category"]
        return {
            "severity": row["severity"],
            "category": category,
            "categoryLabel": self._ANOMALY_CATEGORY_LABELS.get(category, category),
            "message": row["message"],
            "source": row["source"],
        }

    def _serialize_safety_category_row(self, row: sqlite3.Row) -> dict:
        return {
            "key": row["category"],
            "label": row["label"],
            "passed": row["passed_items"],
            "total": row["total_items"],
            "status": row["status"],
        }

    def _serialize_safety_incident_row(self, row: sqlite3.Row) -> dict:
        return {
            "department": row["department"],
            "name": row["victim_name"],
            "gender": row["gender"],
            "occurrenceTime": row["occurrence_time"],
            "injuryType": row["injury_type"],
            "description": row["description"],
        }

    def _safety_trend_maps(
        self, conn: sqlite3.Connection, report_dates: list[str]
    ) -> tuple[dict[str, int], dict[str, int], dict[str, float | None]]:
        if not report_dates:
            return {}, {}, {}
        placeholders = ",".join("?" * len(report_dates))
        incident_rows = conn.execute(
            f"""
            SELECT report_date, COUNT(*) AS incident_count
            FROM safety_incident
            WHERE report_date IN ({placeholders})
            GROUP BY report_date
            """,
            report_dates,
        ).fetchall()
        anomaly_rows = conn.execute(
            f"""
            SELECT report_date, severity, COUNT(*) AS anomaly_count
            FROM anomaly
            WHERE report_date IN ({placeholders})
            GROUP BY report_date, severity
            """,
            report_dates,
        ).fetchall()
        safety_rows = conn.execute(
            f"""
            SELECT report_date, passed_items, total_items
            FROM safety_summary
            WHERE report_date IN ({placeholders})
            """,
            report_dates,
        ).fetchall()

        incident_map = {row["report_date"]: row["incident_count"] for row in incident_rows}
        warning_map: dict[str, int] = {}
        for row in anomaly_rows:
            if row["severity"] in {"WARNING", "CRITICAL"}:
                warning_map[row["report_date"]] = warning_map.get(row["report_date"], 0) + row["anomaly_count"]

        pass_buckets: dict[str, list[sqlite3.Row]] = {date_key: [] for date_key in report_dates}
        for row in safety_rows:
            pass_buckets.setdefault(row["report_date"], []).append(row)
        pass_rate_map = {
            date_key: self._safety_pass_rate(pass_buckets.get(date_key, [])) for date_key in report_dates
        }
        return incident_map, warning_map, pass_rate_map

    def _serialize_safety_trend_rows(
        self,
        report_dates: list[str],
        incident_map: dict[str, int],
        warning_map: dict[str, int],
        pass_rate_map: dict[str, float | None],
    ) -> dict:
        reversed_dates = list(reversed(report_dates))
        return {
            "reportDates": reversed_dates,
            "dates": [date_key[5:] for date_key in reversed_dates],
            "incidentCount": [incident_map.get(date_key, 0) for date_key in reversed_dates],
            "warningCount": [warning_map.get(date_key, 0) for date_key in reversed_dates],
            "safetyPassRate": [pass_rate_map.get(date_key) for date_key in reversed_dates],
        }

    def _serialize_safety_weekday_average(
        self,
        report_dates: list[str],
        incident_map: dict[str, int],
        warning_map: dict[str, int],
        pass_rate_map: dict[str, float | None],
    ) -> dict:
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        buckets: dict[int, list[str]] = {index: [] for index in range(7)}
        for date_key in report_dates:
            weekday = date.fromisoformat(date_key).weekday()
            buckets[weekday].append(date_key)

        def avg_count(weekday: int, metric_map: dict[str, int]) -> float | None:
            values = [metric_map.get(date_key, 0) for date_key in buckets[weekday]]
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        def avg_pass_rate(weekday: int) -> float | None:
            values = [pass_rate_map.get(date_key) for date_key in buckets[weekday] if pass_rate_map.get(date_key) is not None]
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        return {
            "mode": "weekday",
            "labels": weekday_labels,
            "reportDates": weekday_labels,
            "dates": weekday_labels,
            "incidentCount": [avg_count(index, incident_map) for index in range(7)],
            "warningCount": [avg_count(index, warning_map) for index in range(7)],
            "safetyPassRate": [avg_pass_rate(index) for index in range(7)],
            "sampleCounts": [len(buckets[index]) for index in range(7)],
        }

    def _safety_benchmark(
        self,
        incident_map: dict[str, int],
        warning_map: dict[str, int],
        pass_rate_map: dict[str, float | None],
        report_dates: list[str],
    ) -> dict:
        if not report_dates:
            return {
                "incidentCount": None,
                "warningCount": None,
                "safetyPassRate": None,
            }

        incident_values = [incident_map.get(date_key, 0) for date_key in report_dates]
        warning_values = [warning_map.get(date_key, 0) for date_key in report_dates]
        pass_values = [pass_rate_map.get(date_key) for date_key in report_dates if pass_rate_map.get(date_key) is not None]

        return {
            "incidentCount": round(sum(incident_values) / len(incident_values), 1) if incident_values else None,
            "warningCount": round(sum(warning_values) / len(warning_values), 1) if warning_values else None,
            "safetyPassRate": round(sum(pass_values) / len(pass_values), 1) if pass_values else None,
        }

    def _safety_summary(
        self,
        categories: list[sqlite3.Row],
        incidents: list[sqlite3.Row],
        anomalies: list[sqlite3.Row],
    ) -> dict:
        passed_categories = sum(
            1
            for row in categories
            if row["total_items"] and row["passed_items"] == row["total_items"]
        )
        warning_count = sum(1 for row in anomalies if row["severity"] in {"WARNING", "CRITICAL"})
        critical_count = sum(1 for row in anomalies if row["severity"] == "CRITICAL")
        incident_count = len(incidents)
        pass_rate = self._safety_pass_rate(categories)

        if critical_count > 0 or incident_count > 0:
            overall_status = "CRITICAL"
            overall_label = "위험"
        elif warning_count > 0:
            overall_status = "WARNING"
            overall_label = "주의"
        else:
            overall_status = "NORMAL"
            overall_label = "정상"

        return {
            "categoryCount": len(categories),
            "passedCategoryCount": passed_categories,
            "incidentCount": incident_count,
            "warningAnomalyCount": warning_count,
            "criticalAnomalyCount": critical_count,
            "safetyPassRate": pass_rate,
            "overallStatus": overall_status,
            "overallLabel": overall_label,
        }

    def get_safety_analysis(self, report_date: str) -> dict:
        with self._connect() as conn:
            summary_exists = conn.execute(
                "SELECT 1 FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            if not summary_exists:
                return {}

            center = conn.execute(
                "SELECT center_name FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            categories = conn.execute(
                "SELECT * FROM safety_summary WHERE report_date = ? ORDER BY category",
                (report_date,),
            ).fetchall()
            incidents = conn.execute(
                "SELECT * FROM safety_incident WHERE report_date = ? ORDER BY seq",
                (report_date,),
            ).fetchall()
            anomalies = conn.execute(
                "SELECT * FROM anomaly WHERE report_date = ? ORDER BY id",
                (report_date,),
            ).fetchall()
            trend_date_rows = conn.execute(
                """
                SELECT report_date
                FROM daily_summary
                WHERE report_date <= ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()
            prev_date_rows = conn.execute(
                """
                SELECT report_date
                FROM daily_summary
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 30
                """,
                (report_date,),
            ).fetchall()

        trend_dates = [row["report_date"] for row in trend_date_rows]
        prev_dates = [row["report_date"] for row in prev_date_rows]
        benchmark_dates = list(dict.fromkeys(trend_dates + prev_dates))

        with self._connect() as conn:
            incident_map, warning_map, pass_rate_map = self._safety_trend_maps(conn, benchmark_dates)

        trend_7d = trend_dates[:7]
        trend_30d = trend_dates
        trend_30d_series = self._serialize_safety_trend_rows(trend_30d, incident_map, warning_map, pass_rate_map)
        avg7 = prev_dates[:7]
        avg30 = prev_dates[:30]
        weekday_labels = ["월", "화", "수", "목", "금", "토", "일"]
        report_weekday = date.fromisoformat(report_date).weekday()
        same_weekday_dates = [
            date_key
            for date_key in prev_dates
            if date.fromisoformat(date_key).weekday() == report_weekday
        ]
        prev_day_dates = prev_dates[:1]
        current_summary = self._safety_summary(categories, incidents, anomalies)

        return {
            "meta": {
                "reportDate": report_date,
                "centerName": center["center_name"] if center else None,
            },
            "summary": current_summary,
            "safety": {
                "categories": [self._serialize_safety_category_row(row) for row in categories],
                "incidentCount": len(incidents),
                "incidents": [self._serialize_safety_incident_row(row) for row in incidents],
            },
            "anomalies": [self._serialize_anomaly_row(row) for row in anomalies],
            "benchmarks": {
                "prevDay": self._safety_benchmark(incident_map, warning_map, pass_rate_map, prev_day_dates),
                "avg7d": self._safety_benchmark(incident_map, warning_map, pass_rate_map, avg7),
                "avg30d": self._safety_benchmark(incident_map, warning_map, pass_rate_map, avg30),
                "sameWeekday": {
                    **self._safety_benchmark(incident_map, warning_map, pass_rate_map, same_weekday_dates),
                    "weekdayLabel": weekday_labels[report_weekday],
                    "sampleCount": len(same_weekday_dates),
                },
            },
            "trends": {
                "7d": self._serialize_safety_trend_rows(trend_7d, incident_map, warning_map, pass_rate_map),
                "30d": trend_30d_series,
                "weekday": self._serialize_safety_weekday_average(
                    trend_30d, incident_map, warning_map, pass_rate_map
                ),
            },
            "dailyTrend": trend_30d_series,
        }

    def _rebuild_comparisons(self, report_date: date) -> None:
        with self._connect() as conn:
            current = conn.execute(
                "SELECT * FROM daily_summary WHERE report_date = ?",
                (report_date.isoformat(),),
            ).fetchone()
            if not current:
                return

            prev = conn.execute(
                """
                SELECT * FROM daily_summary
                WHERE report_date < ?
                ORDER BY report_date DESC LIMIT 1
                """,
                (report_date.isoformat(),),
            ).fetchone()

            conn.execute(
                "DELETE FROM kpi_comparison WHERE report_date = ? AND compare_basis = 'prev_day'",
                (report_date.isoformat(),),
            )
            if not prev:
                conn.commit()
                return

            metrics = [
                ("total_volume", current["total_volume"], prev["total_volume"]),
                ("dispatch_volume", current["dispatch_volume"], prev["dispatch_volume"]),
                ("arrival_volume", current["arrival_volume"], prev["arrival_volume"]),
                ("national_volume", current["national_volume"], prev["national_volume"]),
                (
                    "national_processing_rate",
                    self._national_processing_rate(current["total_volume"], current["national_volume"]),
                    self._national_processing_rate(prev["total_volume"], prev["national_volume"]),
                ),
                ("productivity", current["productivity"], prev["productivity"]),
                ("ips_rate", current["ips_rate"], prev["ips_rate"]),
            ]
            for metric_name, current_value, compare_value in metrics:
                if current_value is None or compare_value in (None, 0):
                    continue
                difference = current_value - compare_value
                difference_percent = (difference / compare_value) * 100
                trend = "UP" if difference > 0 else "DOWN" if difference < 0 else "STABLE"
                conn.execute(
                    """
                    INSERT INTO kpi_comparison
                    (report_date, metric_name, current_value, compare_value, difference,
                     difference_percent, trend, compare_basis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'prev_day')
                    """,
                    (
                        report_date.isoformat(),
                        metric_name,
                        current_value,
                        compare_value,
                        difference,
                        difference_percent,
                        trend,
                    ),
                )
            conn.commit()

    def list_report_dates(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT report_date FROM daily_summary ORDER BY report_date"
            ).fetchall()
        return [row["report_date"] for row in rows]

    def list_report_date_metadata(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT report_date, report_format, day_type
                FROM report_metadata
                ORDER BY report_date
                """
            ).fetchall()
        return [
            {
                "reportDate": row["report_date"],
                "format": row["report_format"],
                "dayType": row["day_type"],
            }
            for row in rows
        ]

    def list_reports(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    rm.report_date,
                    rm.center_name,
                    rm.report_format,
                    rm.day_type,
                    rm.file_path,
                    rm.ingested_at,
                    SUM(CASE WHEN vl.status IN ('FAIL', 'WARNING') THEN 1 ELSE 0 END) AS validation_issues,
                    SUM(CASE WHEN vl.status = 'FAIL' THEN 1 ELSE 0 END) AS validation_fails,
                    SUM(CASE WHEN vl.status = 'WARNING' THEN 1 ELSE 0 END) AS validation_warnings
                FROM report_metadata rm
                LEFT JOIN validation_log vl ON vl.report_date = rm.report_date
                GROUP BY rm.report_date, rm.center_name, rm.report_format, rm.day_type, rm.file_path, rm.ingested_at
                ORDER BY rm.report_date DESC
                """
            ).fetchall()
        reports: list[dict] = []
        for row in rows:
            file_path = row["file_path"]
            reports.append(
                {
                    "reportDate": row["report_date"],
                    "centerName": row["center_name"],
                    "format": row["report_format"],
                    "dayType": row["day_type"],
                    "filePath": file_path,
                    "fileName": Path(file_path).name if file_path else None,
                    "ingestedAt": row["ingested_at"],
                    "validationIssues": int(row["validation_issues"] or 0),
                    "validationFailCount": int(row["validation_fails"] or 0),
                    "validationWarningCount": int(row["validation_warnings"] or 0),
                    "hasFile": bool(file_path and Path(file_path).exists()),
                    "canDeleteFile": self._is_uploaded_file(file_path),
                }
            )
        return reports

    def _is_uploaded_file(self, file_path: str | None) -> bool:
        if not file_path:
            return False
        path = Path(file_path)
        if not path.exists():
            return False
        uploads_dir = Path(self.db_path).parent / "uploads"
        try:
            path.resolve().relative_to(uploads_dir.resolve())
            return True
        except ValueError:
            return False

    def delete_report(self, report_date: str, *, delete_file: bool = True) -> dict:
        file_path = self.get_report_file_path(report_date)
        tables = [
            "hourly_throughput",
            "staffing",
            "transport_office",
            "safety_summary",
            "safety_incident",
            "anomaly",
            "validation_log",
            "kpi_comparison",
            "quota_exchange",
            "sorting_machine",
            "daily_summary",
            "report_metadata",
        ]

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM report_metadata WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            if not exists:
                return {"deleted": False, "reportDate": report_date}

            for table in tables:
                conn.execute(f"DELETE FROM {table} WHERE report_date = ?", (report_date,))
            conn.commit()

        file_deleted = False
        if delete_file and self._is_uploaded_file(file_path):
            Path(file_path).unlink(missing_ok=True)
            file_deleted = True

        for remaining_date in self.list_report_dates():
            if remaining_date > report_date:
                self._rebuild_comparisons(date.fromisoformat(remaining_date))

        return {
            "deleted": True,
            "reportDate": report_date,
            "fileDeleted": file_deleted,
        }

    def get_report_file_path(self, report_date: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT file_path FROM report_metadata WHERE report_date = ?",
                (report_date,),
            ).fetchone()
        if not row or not row["file_path"]:
            return None
        return row["file_path"]

    def get_validation_logs(self, report_date: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT rule_name, status, details
                FROM validation_log
                WHERE report_date = ?
                ORDER BY rule_name
                """,
                (report_date,),
            ).fetchall()
        logs: list[dict] = []
        for row in rows:
            details = row["details"]
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except json.JSONDecodeError:
                    pass
            logs.append(
                {
                    "ruleName": row["rule_name"],
                    "status": row["status"],
                    "details": details,
                }
            )
        return logs

    def get_system_status(self) -> dict:
        db_path = Path(self.db_path)
        with self._connect() as conn:
            report_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM report_metadata"
            ).fetchone()["cnt"]
            range_row = conn.execute(
                """
                SELECT MIN(report_date) AS earliest_date, MAX(report_date) AS latest_date
                FROM report_metadata
                """
            ).fetchone()
            validation_issues = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM validation_log
                WHERE status IN ('FAIL', 'WARNING')
                """
            ).fetchone()["cnt"]
            anomaly_count = conn.execute("SELECT COUNT(*) AS cnt FROM anomaly").fetchone()["cnt"]
            threshold_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM threshold_config"
            ).fetchone()["cnt"]

        return {
            "dbPath": str(db_path),
            "dbExists": db_path.exists(),
            "dbSizeBytes": db_path.stat().st_size if db_path.exists() else 0,
            "reportCount": int(report_count),
            "earliestDate": range_row["earliest_date"],
            "latestDate": range_row["latest_date"],
            "validationIssues": int(validation_issues),
            "anomalyCount": int(anomaly_count),
            "thresholdCount": int(threshold_count),
        }

    def list_threshold_configs(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metric_name, caution_min, caution_max, warning_min, warning_max,
                       critical_min, critical_max
                FROM threshold_config
                ORDER BY metric_name
                """
            ).fetchall()
        return [
            {
                "metricName": row["metric_name"],
                "cautionMin": row["caution_min"],
                "cautionMax": row["caution_max"],
                "warningMin": row["warning_min"],
                "warningMax": row["warning_max"],
                "criticalMin": row["critical_min"],
                "criticalMax": row["critical_max"],
            }
            for row in rows
        ]

    def update_threshold_config(self, metric_name: str, payload: dict) -> None:
        fields = {
            "cautionMin": "caution_min",
            "cautionMax": "caution_max",
            "warningMin": "warning_min",
            "warningMax": "warning_max",
            "criticalMin": "critical_min",
            "criticalMax": "critical_max",
        }
        updates: list[str] = []
        values: list[float | None] = []
        for key, column in fields.items():
            if key in payload:
                updates.append(f"{column} = ?")
                values.append(payload[key])
        if not updates:
            return
        values.append(metric_name)
        with self._connect() as conn:
            result = conn.execute(
                f"UPDATE threshold_config SET {', '.join(updates)} WHERE metric_name = ?",
                values,
            )
            if result.rowcount == 0:
                raise KeyError(metric_name)
            conn.commit()

    def list_operation_periods(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, period_type, start_date, end_date, note, created_at
                FROM operation_period
                ORDER BY start_date DESC, id DESC
                """
            ).fetchall()
        return [self._serialize_operation_period(row) for row in rows]

    def create_operation_period(self, payload: dict) -> dict:
        period_type = payload.get("periodType")
        start_date = payload.get("startDate")
        end_date = payload.get("endDate") or start_date
        note = payload.get("note")
        if not period_type or not start_date:
            raise ValueError("periodType and startDate are required")
        if end_date < start_date:
            raise ValueError("endDate must be on or after startDate")

        created_at = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO operation_period (period_type, start_date, end_date, note, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (period_type, start_date, end_date, note, created_at),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT id, period_type, start_date, end_date, note, created_at
                FROM operation_period
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        if not row:
            raise RuntimeError("failed to create operation period")
        return self._serialize_operation_period(row)

    def update_operation_period(self, period_id: int, payload: dict) -> dict:
        period_type = payload.get("periodType")
        start_date = payload.get("startDate")
        end_date = payload.get("endDate") or start_date
        note = payload.get("note")
        if not period_type or not start_date:
            raise ValueError("periodType and startDate are required")
        if end_date < start_date:
            raise ValueError("endDate must be on or after startDate")

        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE operation_period
                SET period_type = ?, start_date = ?, end_date = ?, note = ?
                WHERE id = ?
                """,
                (period_type, start_date, end_date, note, period_id),
            )
            if result.rowcount == 0:
                raise KeyError(period_id)
            conn.commit()
            row = conn.execute(
                """
                SELECT id, period_type, start_date, end_date, note, created_at
                FROM operation_period
                WHERE id = ?
                """,
                (period_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("failed to update operation period")
        return self._serialize_operation_period(row)

    def delete_operation_period(self, period_id: int) -> bool:
        with self._connect() as conn:
            result = conn.execute("DELETE FROM operation_period WHERE id = ?", (period_id,))
            conn.commit()
            return result.rowcount > 0

    def _serialize_operation_period(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "periodType": row["period_type"],
            "startDate": row["start_date"],
            "endDate": row["end_date"],
            "note": row["note"],
            "createdAt": row["created_at"],
        }

    def get_dashboard_summary(self, report_date: str, compare_basis: str = "prev_day") -> dict:
        with self._connect() as conn:
            summary = conn.execute(
                "SELECT * FROM daily_summary WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            if not summary:
                return {}
            metadata = conn.execute(
                "SELECT report_format, day_type FROM report_metadata WHERE report_date = ?",
                (report_date,),
            ).fetchone()

            comparisons = self._load_comparisons(conn, report_date, compare_basis)
            hourly = conn.execute(
                "SELECT * FROM hourly_throughput WHERE report_date = ?",
                (report_date,),
            ).fetchall()
            staffing = conn.execute(
                "SELECT * FROM staffing WHERE report_date = ?",
                (report_date,),
            ).fetchall()
            quota = conn.execute(
                "SELECT * FROM quota_exchange WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            sorting = conn.execute(
                "SELECT * FROM sorting_machine WHERE report_date = ?",
                (report_date,),
            ).fetchone()
            offices = conn.execute(
                "SELECT * FROM transport_office WHERE report_date = ?",
                (report_date,),
            ).fetchall()
            anomalies = conn.execute(
                "SELECT * FROM anomaly WHERE report_date = ? LIMIT 5",
                (report_date,),
            ).fetchall()
            safety = conn.execute(
                "SELECT * FROM safety_summary WHERE report_date = ?",
                (report_date,),
            ).fetchall()
            safety_incidents = conn.execute(
                "SELECT * FROM safety_incident WHERE report_date = ? ORDER BY seq",
                (report_date,),
            ).fetchall()
            trend_dates = conn.execute(
                """
                SELECT ds.report_date, ds.total_volume, sm.ips_rate, sm.reject_rate
                FROM daily_summary ds
                LEFT JOIN sorting_machine sm ON ds.report_date = sm.report_date
                WHERE ds.report_date <= ?
                ORDER BY ds.report_date DESC LIMIT 7
                """,
                (report_date,),
            ).fetchall()

        def compare_for(metric: str):
            row = comparisons.get(metric)
            if not row:
                return None
            compare_value = row["compare_value"] if isinstance(row, dict) else row["compare_value"]
            difference_percent = (
                row["difference_percent"] if isinstance(row, dict) else row["difference_percent"]
            )
            trend = row["trend"] if isinstance(row, dict) else row["trend"]
            return {
                "percent": round(difference_percent, 1) if difference_percent is not None else None,
                "trend": trend,
                "compareValue": compare_value,
            }

        def to_thousand(value: int | float | None) -> float | None:
            return self._to_thousand(value)

        def compare_for_thousand(metric: str):
            compare = compare_for(metric)
            if not compare:
                return None
            if compare["compareValue"] is not None:
                compare["compareValue"] = to_thousand(compare["compareValue"])
            return compare

        def volume_kpi(key: str, label: str, value: int | None, **extra):
            return {
                "key": key,
                "label": label,
                "value": to_thousand(value),
                "unit": "천개",
                **extra,
            }

        peak_hour = self._peak_hourly_row(hourly)
        peak_staff = max(staffing, key=lambda row: row["actual_staff"] or 0, default=None)
        ordered_hourly = self._order_hourly_rows(hourly)
        ordered_staffing = self._order_hourly_rows(staffing)

        return {
            "meta": {
                "reportDate": report_date,
                "centerName": summary["center_name"],
                "reportFormat": metadata["report_format"] if metadata else None,
                "dayType": metadata["day_type"] if metadata else None,
                "communicationStatus": summary["communication_status"],
                "communicationStatusLabel": "정상 소통"
                if (summary["remaining_volume"] or 0) == 0
                else "잔량 발생",
                "compareBasis": compare_basis,
            },
            "kpis": [
                {
                    **volume_kpi("national_volume", "전국접수물량", summary["national_volume"]),
                    "compare": compare_for_thousand("national_volume"),
                },
                {
                    **volume_kpi("total_volume", "총 처리물량", summary["total_volume"]),
                    "compare": compare_for_thousand("total_volume"),
                },
                {
                    **volume_kpi("dispatch_volume", "발송물량", summary["dispatch_volume"]),
                    "compare": compare_for_thousand("dispatch_volume"),
                },
                {
                    **volume_kpi("arrival_volume", "도착물량", summary["arrival_volume"]),
                    "compare": compare_for_thousand("arrival_volume"),
                },
                {
                    **volume_kpi(
                        "remaining_volume",
                        "잔량",
                        summary["remaining_volume"],
                    ),
                },
                {
                    "key": "productivity",
                    "label": "인시당 처리량",
                    "value": summary["productivity"],
                    "unit": "개/시",
                    "compare": compare_for("productivity"),
                },
                {
                    "key": "ips_rate",
                    "label": "IPS",
                    "value": summary["ips_rate"],
                    "unit": "%",
                    "compare": compare_for("ips_rate"),
                },
                {
                    "key": "last_operation_time",
                    "label": "최종 작업종료",
                    "value": (summary["last_operation_time"] or "")[:5],
                    "unit": "",
                },
            ],
            "hourlyVolume": {
                "slots": list(HOUR_SLOTS),
                "current": [
                    {
                        "slot": slot,
                        "label": format_hour_label(slot),
                        "dispatch": ordered_hourly[slot]["dispatch_volume"] if ordered_hourly[slot] else None,
                        "arrival": ordered_hourly[slot]["arrival_volume"] if ordered_hourly[slot] else None,
                        "total": ordered_hourly[slot]["total_volume"] if ordered_hourly[slot] else None,
                    }
                    for slot in HOUR_SLOTS
                ],
                "peak": {
                    "slot": peak_hour["hour_slot"] if peak_hour else None,
                    "value": peak_hour["total_volume"] if peak_hour else None,
                },
            },
            "hourlyStaff": {
                "slots": list(HOUR_SLOTS),
                "actualStaff": [
                    {
                        "slot": slot,
                        "label": format_hour_label(slot),
                        "value": ordered_staffing[slot]["actual_staff"] if ordered_staffing[slot] else None,
                    }
                    for slot in HOUR_SLOTS
                ],
                "productivity": [
                    {
                        "slot": slot,
                        "label": format_hour_label(slot),
                        "value": ordered_staffing[slot]["productivity"] if ordered_staffing[slot] else None,
                    }
                    for slot in HOUR_SLOTS
                ],
                "peakStaff": {
                    "slot": peak_staff["hour_slot"] if peak_staff else None,
                    "value": peak_staff["actual_staff"] if peak_staff else None,
                },
            },
            "anomalies": [
                {
                    "severity": row["severity"],
                    "category": row["category"],
                    "message": row["message"],
                }
                for row in anomalies
            ],
            "equipment": {
                "sortingRate": sorting["sorting_rate"] if sorting else None,
                "ipsRate": sorting["ips_rate"] if sorting else None,
                "rejectRate": sorting["reject_rate"] if sorting else None,
                "shortcutRate": sorting["shortcut_rate"] if sorting else None,
                "avgThroughput": sorting["avg_throughput"] if sorting else None,
                "peakThroughput": sorting["peak_throughput"] if sorting else None,
                "unreadCount": sorting["unread_count"] if sorting else None,
                "unreadRate": sorting["unread_rate"] if sorting else None,
                "ipsTarget": 97.0,
            },
            "trend7d": {
                "dates": [row["report_date"][5:] for row in reversed(trend_dates)],
                "totalVolume": [row["total_volume"] for row in reversed(trend_dates)],
                "ipsRate": [row["ips_rate"] for row in reversed(trend_dates)],
                "rejectRate": [row["reject_rate"] for row in reversed(trend_dates)],
            },
            "transport": {
                "quarter": {
                    "actual": quota["quarter_actual"] if quota else None,
                    "standard": quota["quarter_standard"] if quota else None,
                    "complianceRate": round((quota["quarter_actual"] / quota["quarter_standard"]) * 100, 1)
                    if quota and quota["quarter_actual"] and quota["quarter_standard"]
                    else None,
                },
                "exchange": {
                    "actual": quota["exchange_actual"] if quota else None,
                    "standard": quota["exchange_standard"] if quota else None,
                    "complianceRate": round((quota["exchange_actual"] / quota["exchange_standard"]) * 100, 1)
                    if quota and quota["exchange_actual"] and quota["exchange_standard"]
                    else None,
                },
                "exchangeRemaining": quota["exchange_remaining"] if quota else None,
            },
            "quotaOverages": [
                self._serialize_office_row(row)
                for row in offices
                if self._office_is_quota_overage(row)
            ],
            "officeArrivals": [self._serialize_office_row(row) for row in offices],
            "safety": {
                "categories": [
                    {
                        "key": row["category"],
                        "label": row["label"],
                        "passed": row["passed_items"],
                        "total": row["total_items"],
                        "status": row["status"],
                    }
                    for row in safety
                ],
                "incidentCount": len(safety_incidents),
                "incidents": [
                    {
                        "department": row["department"],
                        "name": row["victim_name"],
                        "gender": row["gender"],
                        "occurrenceTime": row["occurrence_time"],
                        "injuryType": row["injury_type"],
                        "description": row["description"],
                    }
                    for row in safety_incidents
                ],
            },
        }

    def get_volume_forecast_context(self, report_date: str) -> dict:
        """전망 대상일(day_type)에 맞는 과거 물량만 추출해 Seasonal Naive 입력값을 만든다."""
        report_day = date.fromisoformat(report_date)
        target = resolve_forecast_target_date(report_day)
        target_day_type = resolve_day_type(target)
        target_weekday = target.weekday()
        today_day_type = resolve_day_type(report_day)
        today_weekday = report_day.weekday()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ds.report_date, ds.total_volume
                FROM daily_summary ds
                WHERE ds.report_date <= ?
                ORDER BY ds.report_date DESC
                LIMIT 90
                """,
                (report_date,),
            ).fetchall()

        def row_day_type(row_date: str) -> str:
            return resolve_day_type(date.fromisoformat(row_date))

        def matches_target(row: sqlite3.Row) -> bool:
            row_type = row_day_type(row["report_date"])
            if row_type != target_day_type:
                return False
            if target_day_type == "weekday":
                return date.fromisoformat(row["report_date"]).weekday() == target_weekday
            return True

        def matches_today(row: sqlite3.Row) -> bool:
            row_type = row_day_type(row["report_date"])
            if row_type != today_day_type:
                return False
            if today_day_type == "weekday":
                return date.fromisoformat(row["report_date"]).weekday() == today_weekday
            return True

        def avg_thousand(subset: list[sqlite3.Row]) -> float | None:
            values = [row["total_volume"] for row in subset if row["total_volume"] is not None]
            if not values:
                return None
            return self._to_thousand(sum(values) / len(values))

        past_rows = [row for row in rows if row["report_date"] != report_date]
        target_rows = [row for row in past_rows if matches_target(row)]
        today_rows = [row for row in past_rows if matches_today(row)]

        today_row = next((row for row in rows if row["report_date"] == report_date), None)
        today_volume = self._to_thousand(today_row["total_volume"]) if today_row else None

        recent_chronological = [
            self._to_thousand(row["total_volume"])
            for row in reversed(target_rows[:7])
            if row["total_volume"] is not None
        ]

        seasonal_naive_1w = (
            self._to_thousand(target_rows[0]["total_volume"])
            if target_rows and target_rows[0]["total_volume"] is not None
            else None
        )

        operation_periods = self.list_operation_periods()
        target_periods = get_operation_periods_for_date(target, operation_periods)
        volume_by_date = {
            row["report_date"]: self._to_thousand(row["total_volume"])
            for row in rows
            if row["total_volume"] is not None
        }
        historical_no_parcel_avg = compute_historical_no_parcel_avg(
            operation_periods,
            volume_by_date,
            target,
        )

        return {
            "forecastTargetDate": target.isoformat(),
            "forecastTargetNote": forecast_target_note_for(report_day, target),
            "tomorrowDayType": target_day_type,
            "todayVolume": today_volume,
            "sameTypeBaseline": avg_thousand(target_rows[:30]),
            "sameTypeSampleCount": min(len(target_rows), 30),
            "sameTypeAvg7d": avg_thousand(target_rows[:7]),
            "sameTypeAvg30d": avg_thousand(target_rows[:30]),
            "sameTypeRecent7d": recent_chronological,
            "todayTypeAvg7d": avg_thousand(today_rows[:7]),
            "seasonalNaive1w": seasonal_naive_1w,
            "seasonalNaive4w": avg_thousand(target_rows[:4]),
            "operationPeriods": operation_periods,
            "targetOperationPeriodLabels": operation_period_labels(target_periods),
            "historicalNoParcelAvg": historical_no_parcel_avg,
            "volumeByDate": {
                report_key: volume
                for report_key, volume in volume_by_date.items()
                if volume is not None
            },
        }

    def get_volume_ml_timeseries(self, through_date: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ds.report_date,
                    ds.total_volume,
                    ds.national_volume,
                    ds.remaining_volume,
                    rm.day_type,
                    rm.report_format
                FROM daily_summary ds
                LEFT JOIN report_metadata rm ON rm.report_date = ds.report_date
                WHERE ds.report_date <= ?
                ORDER BY ds.report_date ASC
                """,
                (through_date,),
            ).fetchall()

        return [
            {
                "reportDate": row["report_date"],
                "totalVolume": row["total_volume"],
                "nationalVolume": row["national_volume"],
                "remainingVolume": row["remaining_volume"],
                "dayType": row["day_type"],
                "reportFormat": row["report_format"],
            }
            for row in rows
        ]

    def get_hourly_volume_pattern(self, report_date: str, limit: int = 30) -> dict:
        with self._connect() as conn:
            date_rows = conn.execute(
                """
                SELECT report_date
                FROM daily_summary
                WHERE report_date <= ?
                ORDER BY report_date DESC
                LIMIT ?
                """,
                (report_date, limit),
            ).fetchall()
            if not date_rows:
                return {
                    "slots": list(HOUR_SLOTS),
                    "labels": [format_hour_label(slot) for slot in HOUR_SLOTS],
                    "averageVolume": [None for _ in HOUR_SLOTS],
                    "peakHour": None,
                    "peakHourVolume": None,
                    "sampleDays": 0,
                }

            report_dates = [row["report_date"] for row in date_rows]
            placeholders = ",".join("?" * len(report_dates))
            rows = conn.execute(
                f"""
                SELECT hour_slot, AVG(total_volume) AS avg_volume
                FROM hourly_throughput
                WHERE report_date IN ({placeholders})
                GROUP BY hour_slot
                """,
                report_dates,
            ).fetchall()

        slot_avg: dict[str, float] = {}
        for row in rows:
            if row["avg_volume"] is None:
                continue
            slot = normalize_hour_slot(str(row["hour_slot"]))
            slot_avg[slot] = float(row["avg_volume"])

        averages = [self._to_thousand(slot_avg.get(slot)) for slot in HOUR_SLOTS]
        active_slots = [(slot, slot_avg[slot]) for slot in HOUR_SLOTS if slot_avg.get(slot, 0) > 0]
        peak_slot = max(active_slots, key=lambda item: item[1])[0] if active_slots else None

        return {
            "slots": list(HOUR_SLOTS),
            "labels": [format_hour_label(slot) for slot in HOUR_SLOTS],
            "averageVolume": averages,
            "peakHour": format_hour_label(peak_slot) if peak_slot else None,
            "peakHourVolume": self._to_thousand(slot_avg.get(peak_slot)) if peak_slot else None,
            "sampleDays": len(report_dates),
        }

    def _peak_hourly_row(self, rows: list[sqlite3.Row]) -> sqlite3.Row | None:
        active_rows = [row for row in rows if (row["total_volume"] or 0) > 0]
        if not active_rows:
            return None
        return max(active_rows, key=lambda row: row["total_volume"] or 0)

    def _order_hourly_rows(self, rows: list[sqlite3.Row]) -> dict[str, sqlite3.Row | None]:
        indexed: dict[str, sqlite3.Row] = {}
        for row in rows:
            slot = normalize_hour_slot(str(row["hour_slot"]))
            indexed[slot] = row
        return {slot: indexed.get(slot) for slot in HOUR_SLOTS}
