"""로컬 SQLite 운영 설정을 프로덕션 API로 동기화합니다."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx

DEFAULT_API = "https://imc-dashboard-api-production-2929.up.railway.app"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "imc_dashboard.db"


def _load_password_from_railway() -> str:
    raw = subprocess.check_output(
        ["railway", "variables", "--json"],
        text=True,
        cwd=PROJECT_ROOT,
    )
    password = json.loads(raw).get("IMC_ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("IMC_ADMIN_PASSWORD not found in Railway variables")
    return password


def _admin_headers(client: httpx.Client, api_base: str, password: str) -> dict[str, str]:
    response = client.post(
        f"{api_base}/api/admin/verify",
        json={"password": password},
        timeout=30.0,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("admin verify succeeded but token missing")
    return {"Authorization": f"Bearer {token}"}


def _load_local_periods(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT period_type, start_date, end_date, note
        FROM operation_period
        ORDER BY start_date, id
        """
    ).fetchall()
    conn.close()
    return [
        {
            "periodType": row["period_type"],
            "startDate": row["start_date"],
            "endDate": row["end_date"],
            "note": row["note"],
        }
        for row in rows
    ]


def _load_local_thresholds(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT metric_name, caution_min, caution_max, warning_min, warning_max,
               critical_min, critical_max
        FROM threshold_config
        ORDER BY metric_name
        """
    ).fetchall()
    conn.close()
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


def _period_key(period: dict) -> tuple:
    return (
        period.get("periodType"),
        period.get("startDate"),
        period.get("endDate"),
        period.get("note") or "",
    )


def sync_config(
    db_path: Path,
    api_base: str,
    password: str,
) -> int:
    local_periods = _load_local_periods(db_path)
    local_thresholds = _load_local_thresholds(db_path)

    created = 0
    skipped = 0
    threshold_updates = 0

    with httpx.Client() as client:
        headers = _admin_headers(client, api_base, password)

        remote_response = client.get(f"{api_base}/api/operation-periods", timeout=30.0)
        remote_response.raise_for_status()
        remote_periods = remote_response.json().get("periods", [])
        remote_keys = {_period_key(period) for period in remote_periods}

        for period in local_periods:
            key = _period_key(period)
            if key in remote_keys:
                skipped += 1
                continue
            response = client.post(
                f"{api_base}/api/operation-periods",
                headers=headers,
                json=period,
                timeout=30.0,
            )
            response.raise_for_status()
            created += 1
            remote_keys.add(key)
            print(f"  + period {period['periodType']} {period['startDate']}~{period['endDate']}")

        remote_thresholds = client.get(f"{api_base}/api/system/thresholds", timeout=30.0)
        remote_thresholds.raise_for_status()
        remote_by_metric = {
            item["metricName"]: item
            for item in remote_thresholds.json().get("thresholds", [])
        }

        for threshold in local_thresholds:
            metric_name = threshold["metricName"]
            payload = {k: v for k, v in threshold.items() if k != "metricName"}
            remote = remote_by_metric.get(metric_name, {})
            if all(remote.get(key) == value for key, value in payload.items()):
                continue
            response = client.put(
                f"{api_base}/api/system/thresholds/{metric_name}",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            threshold_updates += 1
            print(f"  ~ threshold {metric_name}")

    print(
        f"\nDone. periods created={created} skipped={skipped}, "
        f"thresholds updated={threshold_updates}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local operation config to production")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"FAIL: database not found: {args.db}")
        raise SystemExit(1)

    password = (args.password or _load_password_from_railway()).strip()
    raise SystemExit(sync_config(args.db, args.api.rstrip("/"), password))


if __name__ == "__main__":
    main()
