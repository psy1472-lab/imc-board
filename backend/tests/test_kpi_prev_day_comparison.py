from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure.db.sqlite_repository import SqliteRepository


def _insert_summary(conn, report_date: str, **values) -> None:
    conn.execute(
        """
        INSERT INTO daily_summary (
            report_date, center_name, national_volume, total_volume,
            dispatch_volume, arrival_volume, remaining_volume, productivity, ips_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_date,
            "중부권IMC",
            values.get("national_volume"),
            values.get("total_volume"),
            values.get("dispatch_volume"),
            values.get("arrival_volume"),
            values.get("remaining_volume", 0),
            values.get("productivity"),
            values.get("ips_rate"),
        ),
    )


def test_prev_day_comparison_uses_live_previous_summary_not_stale_store():
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo = SqliteRepository(str(Path(tmp) / "test.db"))
        with repo._connect() as conn:
            _insert_summary(
                conn,
                "2026-10-05",
                national_volume=None,
                total_volume=56476,
                dispatch_volume=48918,
                arrival_volume=7558,
                remaining_volume=0,
                ips_rate=97.57,
            )
            _insert_summary(
                conn,
                "2026-10-06",
                national_volume=1764000,
                total_volume=577000,
                dispatch_volume=404000,
                arrival_volume=173000,
                remaining_volume=3000,
                productivity=202,
                ips_rate=97.44,
            )
            conn.execute(
                """
                INSERT INTO kpi_comparison
                (report_date, metric_name, current_value, compare_value, difference,
                 difference_percent, trend, compare_basis)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'prev_day')
                """,
                ("2026-10-06", "total_volume", 577000, 28050, 548950, 1957.0, "UP"),
            )
            conn.commit()

        summary = repo.get_dashboard_summary("2026-10-06", "prev_day")
        total = next(item for item in summary["kpis"] if item["key"] == "total_volume")
        remaining = next(item for item in summary["kpis"] if item["key"] == "remaining_volume")

        assert total["value"] == 577.0
        assert total["compare"]["compareValue"] == 56.5
        assert total["compare"]["difference"] == 520.5
        assert total["compare"]["percent"] == 921.2
        assert total["compare"]["trend"] == "UP"
        assert remaining["compare"]["compareValue"] == 0
        assert remaining["compare"]["difference"] == 3.0
        assert remaining["compare"]["trend"] == "UP"
