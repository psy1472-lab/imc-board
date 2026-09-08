"""프로덕션 공개 API 스모크 검증 (비밀번호 불필요)."""

from __future__ import annotations

import argparse
import sys

import httpx

DEFAULT_API = "https://imc-dashboard-api-production-2929.up.railway.app"
DEFAULT_VERCEL = "https://frontend-flame-tau-97.vercel.app"


def run_smoke(api_base: str, vercel_base: str) -> int:
    failures: list[str] = []

    with httpx.Client(timeout=30.0) as client:
        for label, base in [("railway", api_base), ("vercel", vercel_base)]:
            try:
                health = client.get(f"{base}/api/health")
                body = health.json()
                if health.status_code != 200 or body.get("status") != "ok":
                    failures.append(f"{label} health failed")
                elif body.get("database", {}).get("reportCount", 0) < 1:
                    failures.append(f"{label} reportCount is zero")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{label} health error: {exc}")

        try:
            dates = client.get(f"{api_base}/api/reports/dates").json().get("dates", [])
            if not dates:
                failures.append("no report dates")
            else:
                latest = dates[-1]
                summary = client.get(
                    f"{api_base}/api/dashboard/summary",
                    params={"date": latest},
                )
                kpis = summary.json().get("kpis", [])
                total = next((k for k in kpis if k.get("key") == "total_volume"), None)
                if summary.status_code != 200 or not total or total.get("value") is None:
                    failures.append(f"summary missing total_volume for {latest}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"summary check error: {exc}")

        try:
            periods = client.get(f"{api_base}/api/operation-periods").json().get("periods", [])
            if not periods:
                failures.append("operation periods not configured")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"operation periods error: {exc}")

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1

    print("PASS: production public smoke")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Production public API smoke test")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--vercel", default=DEFAULT_VERCEL)
    args = parser.parse_args()
    raise SystemExit(run_smoke(args.api.rstrip("/"), args.vercel.rstrip("/")))


if __name__ == "__main__":
    main()
