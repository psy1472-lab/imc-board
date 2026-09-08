"""프로덕션 API·Vercel 프록시 스모크 UAT."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAILWAY = "https://imc-dashboard-api-production-2929.up.railway.app"
DEFAULT_VERCEL = "https://frontend-flame-tau-97.vercel.app"


def _load_password_from_railway() -> str:
    raw = subprocess.check_output(
        ["railway", "variables", "--json"],
        text=True,
        cwd=PROJECT_ROOT,
    )
    variables = json.loads(raw)
    password = variables.get("IMC_ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("IMC_ADMIN_PASSWORD not found in Railway variables")
    return password


def run_smoke(
    railway_base: str,
    vercel_base: str,
    password: str,
) -> int:
    checks: list[tuple[str, bool, str]] = []

    with httpx.Client() as client:
        for label, base in [("Railway health", railway_base), ("Vercel proxy health", vercel_base)]:
            try:
                response = client.get(f"{base}/api/health", timeout=20.0)
                body = response.json()
                ok = (
                    response.status_code == 200
                    and body.get("status") == "ok"
                    and body.get("adminAuth", {}).get("usingFallback") is False
                )
                detail = (
                    f"reportCount={body.get('database', {}).get('reportCount', '?')}, "
                    f"pwLen={body.get('adminAuth', {}).get('passwordLength', '?')}"
                )
                checks.append((label, ok, detail))
            except Exception as exc:  # noqa: BLE001
                checks.append((label, False, str(exc)))

        try:
            response = client.post(
                f"{railway_base}/api/admin/verify",
                json={"password": password},
                timeout=20.0,
            )
            token = response.json().get("token", "") if response.status_code == 200 else ""
            checks.append(
                (
                    "Admin verify",
                    response.status_code == 200 and bool(token),
                    f"status={response.status_code}",
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(("Admin verify", False, str(exc)))
            token = ""

        for label, base in [("Report dates (Railway)", railway_base), ("Report dates (Vercel)", vercel_base)]:
            try:
                response = client.get(f"{base}/api/reports/dates", timeout=20.0)
                dates = response.json().get("dates", [])
                checks.append((label, response.status_code == 200 and len(dates) > 0, f"count={len(dates)}"))
            except Exception as exc:  # noqa: BLE001
                checks.append((label, False, str(exc)))

        try:
            dates_response = client.get(f"{railway_base}/api/reports/dates", timeout=20.0)
            dates = dates_response.json().get("dates", [])
            latest = dates[-1] if dates else None
            if latest:
                summary = client.get(
                    f"{railway_base}/api/dashboard/summary",
                    params={"date": latest},
                    timeout=30.0,
                )
                body = summary.json()
                kpis = body.get("kpis", [])
                total_kpi = next((k for k in kpis if k.get("key") == "total_volume"), None)
                ok = summary.status_code == 200 and total_kpi is not None and total_kpi.get("value") is not None
                checks.append(
                    (
                        f"Summary KPI ({latest})",
                        ok,
                        f"totalVolume={total_kpi.get('value') if total_kpi else None}",
                    )
                )
            else:
                checks.append(("Summary KPI", False, "no report dates"))
        except Exception as exc:  # noqa: BLE001
            checks.append(("Summary KPI", False, str(exc)))

        if token:
            try:
                response = client.get(
                    f"{vercel_base}/api/system/status",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20.0,
                )
                body = response.json()
                ok = response.status_code == 200 and body.get("reportCount", 0) > 0
                checks.append(
                    (
                        "System status (admin)",
                        ok,
                        f"reportCount={body.get('reportCount', '?')}",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                checks.append(("System status (admin)", False, str(exc)))

        try:
            periods_response = client.get(f"{vercel_base}/api/operation-periods", timeout=20.0)
            periods = periods_response.json().get("periods", [])
            active_for_latest = False
            if periods:
                dates_response = client.get(f"{railway_base}/api/reports/dates", timeout=20.0)
                dates = dates_response.json().get("dates", [])
                latest = dates[-1] if dates else None
                if latest:
                    active_for_latest = any(
                        period.get("startDate") <= latest <= period.get("endDate", latest)
                        for period in periods
                    )
            checks.append(
                (
                    "Operation periods",
                    periods_response.status_code == 200 and len(periods) > 0,
                    f"count={len(periods)}, activeForLatest={active_for_latest}",
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(("Operation periods", False, str(exc)))

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print(f"Production UAT: {passed}/{total} passed\n")
    for label, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}: {detail}")

    return 0 if passed == total else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Production smoke UAT")
    parser.add_argument("--railway", default=DEFAULT_RAILWAY)
    parser.add_argument("--vercel", default=DEFAULT_VERCEL)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    password = (args.password or _load_password_from_railway()).strip()
    raise SystemExit(
        run_smoke(
            args.railway.rstrip("/"),
            args.vercel.rstrip("/"),
            password,
        )
    )


if __name__ == "__main__":
    main()
