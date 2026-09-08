"""전체 DB 데이터 정확성 검증 스크립트."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
PRIMARY_DB = BASE / "data" / "imc_dashboard.db"


def _loads_details(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def check_db(db_path: Path) -> dict:
    result: dict = {"path": str(db_path), "exists": db_path.exists()}
    if not db_path.exists():
        return result

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    reports = conn.execute(
        "SELECT report_date, file_path FROM report_metadata ORDER BY report_date"
    ).fetchall()
    result["report_count"] = len(reports)
    if reports:
        result["date_range"] = {
            "from": reports[0]["report_date"],
            "to": reports[-1]["report_date"],
        }

    # 기존 validation_log 집계
    val_rows = conn.execute(
        """
        SELECT status, rule_name, COUNT(*) AS cnt
        FROM validation_log
        GROUP BY status, rule_name
        ORDER BY rule_name, status
        """
    ).fetchall()
    result["stored_validation_summary"] = [dict(r) for r in val_rows]

    stored_issues = conn.execute(
        """
        SELECT report_date, rule_name, status, details
        FROM validation_log
        WHERE status IN ('FAIL', 'WARNING')
        ORDER BY report_date, rule_name
        """
    ).fetchall()
    result["stored_validation_issues"] = [
        {**dict(r), "details": _loads_details(r["details"])} for r in stored_issues
    ]

    cross_checks: list[dict] = []

    # 1. 발송 + 도착 = 총 처리물량
    for row in conn.execute(
        """
        SELECT report_date, dispatch_volume, arrival_volume, total_volume
        FROM daily_summary
        ORDER BY report_date
        """
    ).fetchall():
        d, a, t = row["dispatch_volume"], row["arrival_volume"], row["total_volume"]
        if d is not None and a is not None and t is not None:
            expected = d + a
            if expected != t:
                cross_checks.append(
                    {
                        "rule": "dispatch_plus_arrival_equals_total",
                        "report_date": row["report_date"],
                        "status": "FAIL",
                        "details": {
                            "dispatch": d,
                            "arrival": a,
                            "total": t,
                            "expected": expected,
                            "diff": t - expected,
                        },
                    }
                )

    # 2. 시간대별 합계 = 일일 처리물량
    hourly_sums = {
        r["report_date"]: r["hourly_total"]
        for r in conn.execute(
            """
            SELECT report_date, SUM(total_volume) AS hourly_total
            FROM hourly_throughput
            GROUP BY report_date
            """
        ).fetchall()
    }
    for row in conn.execute(
        "SELECT report_date, total_volume FROM daily_summary"
    ).fetchall():
        date = row["report_date"]
        dt = row["total_volume"]
        ht = hourly_sums.get(date)
        if dt is not None and ht is not None and ht != dt:
            cross_checks.append(
                {
                    "rule": "hourly_sum_equals_total",
                    "report_date": date,
                    "status": "WARNING",
                    "details": {
                        "hourly_total": ht,
                        "total": dt,
                        "diff": dt - ht,
                    },
                }
            )

    # 3. 시간대별 발송+도착 = 시간대 총량
    for row in conn.execute(
        """
        SELECT report_date, hour_slot, dispatch_volume, arrival_volume, total_volume
        FROM hourly_throughput
        WHERE dispatch_volume IS NOT NULL
          AND arrival_volume IS NOT NULL
          AND total_volume IS NOT NULL
        """
    ).fetchall():
        expected = row["dispatch_volume"] + row["arrival_volume"]
        if expected != row["total_volume"]:
            cross_checks.append(
                {
                    "rule": "hourly_dispatch_plus_arrival",
                    "report_date": row["report_date"],
                    "status": "WARNING",
                    "details": {
                        "hour_slot": row["hour_slot"],
                        "dispatch": row["dispatch_volume"],
                        "arrival": row["arrival_volume"],
                        "total": row["total_volume"],
                        "expected": expected,
                    },
                }
            )

    # 4. 구분수 <= 공급수
    for row in conn.execute(
        "SELECT report_date, total_sorted, total_supply FROM sorting_machine"
    ).fetchall():
        s, sup = row["total_sorted"], row["total_supply"]
        if s is not None and sup is not None and s > sup:
            cross_checks.append(
                {
                    "rule": "sorted_lte_supply",
                    "report_date": row["report_date"],
                    "status": "FAIL",
                    "details": {"sorted": s, "supply": sup},
                }
            )

    # 5. 구분율 = 구분수/공급수 (±0.5%p)
    for row in conn.execute(
        """
        SELECT report_date, total_sorted, total_supply, sorting_rate
        FROM sorting_machine
        WHERE total_supply > 0 AND sorting_rate IS NOT NULL
        """
    ).fetchall():
        computed = round(row["total_sorted"] / row["total_supply"] * 100, 2)
        stored = round(row["sorting_rate"], 2)
        if abs(computed - stored) > 0.5:
            cross_checks.append(
                {
                    "rule": "sorting_rate_consistency",
                    "report_date": row["report_date"],
                    "status": "WARNING",
                    "details": {
                        "stored_rate": stored,
                        "computed_rate": computed,
                    },
                }
            )

    # 6. 쿼터 차이 = 실제 - 기준
    for row in conn.execute(
        """
        SELECT report_date, quarter_standard, quarter_actual, quarter_difference,
               exchange_standard, exchange_actual, exchange_difference
        FROM quota_exchange
        """
    ).fetchall():
        for prefix in ("quarter", "exchange"):
            std = row[f"{prefix}_standard"]
            act = row[f"{prefix}_actual"]
            diff = row[f"{prefix}_difference"]
            if std is not None and act is not None and diff is not None:
                expected = act - std
                if expected != diff:
                    cross_checks.append(
                        {
                            "rule": f"{prefix}_difference_consistency",
                            "report_date": row["report_date"],
                            "status": "WARNING",
                            "details": {
                                "standard": std,
                                "actual": act,
                                "stored_diff": diff,
                                "expected_diff": expected,
                            },
                        }
                    )

    # 7. 전국접수 대비 처리율 합리성
    for row in conn.execute(
        """
        SELECT report_date, total_volume, national_volume
        FROM daily_summary
        WHERE national_volume IS NOT NULL AND national_volume > 0
        """
    ).fetchall():
        rate = round(row["total_volume"] / row["national_volume"] * 100, 2)
        if rate > 105 or rate < 50:
            cross_checks.append(
                {
                    "rule": "processing_rate_sanity",
                    "report_date": row["report_date"],
                    "status": "WARNING",
                    "details": {
                        "total": row["total_volume"],
                        "national": row["national_volume"],
                        "rate_percent": rate,
                    },
                }
            )

    # 8. raw_values 보존 여부
    missing_raw = conn.execute(
        """
        SELECT report_date FROM daily_summary
        WHERE raw_values IS NULL OR raw_values = '' OR raw_values = '{}'
        """
    ).fetchall()
    if missing_raw:
        cross_checks.append(
            {
                "rule": "raw_values_present",
                "report_date": "multiple",
                "status": "WARNING",
                "details": {
                    "count": len(missing_raw),
                    "sample_dates": [r["report_date"] for r in missing_raw[:5]],
                },
            }
        )

    # 9. 필수 KPI 누락
    for row in conn.execute(
        """
        SELECT report_date, total_volume, dispatch_volume, arrival_volume
        FROM daily_summary
        WHERE total_volume IS NULL
           OR dispatch_volume IS NULL
           OR arrival_volume IS NULL
        """
    ).fetchall():
        cross_checks.append(
            {
                "rule": "required_volume_fields",
                "report_date": row["report_date"],
                "status": "FAIL",
                "details": dict(row),
            }
        )

    result["cross_checks_total"] = len(cross_checks)
    result["cross_check_issues"] = [
        c for c in cross_checks if c["status"] in ("FAIL", "WARNING")
    ]

    # 규칙별 집계
    by_rule: dict[str, dict[str, int]] = {}
    for item in cross_checks:
        rule = item["rule"]
        status = item["status"]
        by_rule.setdefault(rule, {})
        by_rule[rule][status] = by_rule[rule].get(status, 0) + 1
    result["cross_check_by_rule"] = by_rule

    # 보고서별 이슈 수
    per_report: dict[str, int] = {}
    for item in result["cross_check_issues"]:
        d = item["report_date"]
        per_report[d] = per_report.get(d, 0) + 1
    worst = sorted(per_report.items(), key=lambda x: -x[1])[:10]
    result["worst_reports"] = [{"report_date": d, "issue_count": n} for d, n in worst]

    # 전체 PASS 비율
    fail_reports = {
        i["report_date"]
        for i in result["cross_check_issues"]
        if i["status"] == "FAIL" and i["report_date"] != "multiple"
    }
    warn_reports = {
        i["report_date"]
        for i in result["cross_check_issues"]
        if i["status"] == "WARNING" and i["report_date"] != "multiple"
    }
    total = result["report_count"] or 0
    result["summary"] = {
        "reports_with_fail": len(fail_reports),
        "reports_with_warning": len(warn_reports),
        "clean_reports": total - len(fail_reports | warn_reports),
        "clean_rate_percent": round(
            (total - len(fail_reports | warn_reports)) / total * 100, 1
        )
        if total
        else 0,
    }

    conn.close()
    return result


def main() -> int:
    result = check_db(PRIMARY_DB)
    out_path = Path(__file__).resolve().parent / "validation_report.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"Full report: {out_path}")
    has_issues = bool(
        result.get("stored_validation_issues") or result.get("cross_check_issues")
    )
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
