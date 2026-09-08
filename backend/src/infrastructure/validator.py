from __future__ import annotations

from domain.entities import ParsedReport
from domain.format_profile import COMPACT_PROFILE, STANDARD_PROFILE


class DataValidator:
    def validate(self, report: ParsedReport) -> list[dict]:
        profile = COMPACT_PROFILE if report.report_format == "compact" else STANDARD_PROFILE
        return self._validate_with_profile(report, profile)

    def _validate_with_profile(self, report: ParsedReport, profile) -> list[dict]:
        logs: list[dict] = []
        summary = report.daily_summary
        profile_name = report.report_format

        if profile.validation_profile == "standard":
            logs.extend(self._validate_dispatch_arrival_total(summary))
            logs.extend(self._validate_hourly_total(report, strict=True))
        else:
            logs.extend(self._validate_dispatch_arrival_total_compact(summary))
            logs.extend(self._validate_hourly_total(report, strict=False))

        logs.extend(self._validate_sorting_machine(report))
        return [{**log, "profile": profile_name} for log in logs]

    def _validate_dispatch_arrival_total(self, summary) -> list[dict]:
        if (
            summary.dispatch_volume is None
            or summary.arrival_volume is None
            or summary.total_volume is None
        ):
            return []
        expected = summary.dispatch_volume + summary.arrival_volume
        status = "PASS" if expected == summary.total_volume else "FAIL"
        return [
            {
                "rule_name": "dispatch_plus_arrival_equals_total",
                "status": status,
                "details": {
                    "dispatch": summary.dispatch_volume,
                    "arrival": summary.arrival_volume,
                    "total": summary.total_volume,
                    "expected": expected,
                },
            }
        ]

    def _validate_dispatch_arrival_total_compact(self, summary) -> list[dict]:
        if (
            summary.dispatch_volume is None
            or summary.arrival_volume is None
            or summary.total_volume is None
        ):
            return []
        expected = summary.dispatch_volume + summary.arrival_volume
        if expected == summary.total_volume:
            status = "PASS"
        else:
            # 축약형은 '배분' 합계가 총량과 다를 수 있어 FAIL 대신 WARNING
            status = "WARNING"
        return [
            {
                "rule_name": "dispatch_plus_arrival_equals_total",
                "status": status,
                "details": {
                    "dispatch": summary.dispatch_volume,
                    "arrival": summary.arrival_volume,
                    "total": summary.total_volume,
                    "expected": expected,
                    "note": "compact_format_distribution_semantics",
                },
            }
        ]

    def _validate_hourly_total(self, report: ParsedReport, *, strict: bool) -> list[dict]:
        summary = report.daily_summary
        hourly_total = sum(item.total_volume or 0 for item in report.hourly_throughput)
        if summary.total_volume is None or not report.hourly_throughput:
            return []
        if hourly_total == summary.total_volume:
            status = "PASS"
        elif strict:
            status = "WARNING"
        else:
            diff_ratio = abs(hourly_total - summary.total_volume) / max(summary.total_volume, 1)
            status = "PASS" if diff_ratio <= 0.05 else "WARNING"
        return [
            {
                "rule_name": "hourly_sum_equals_total",
                "status": status,
                "details": {"hourly_total": hourly_total, "total": summary.total_volume},
            }
        ]

    def _validate_sorting_machine(self, report: ParsedReport) -> list[dict]:
        machine = report.sorting_machine
        if machine and machine.total_sorted is not None and machine.total_supply is not None:
            status = "PASS" if machine.total_sorted <= machine.total_supply else "FAIL"
            return [
                {
                    "rule_name": "sorted_lte_supply",
                    "status": status,
                    "details": {
                        "sorted": machine.total_sorted,
                        "supply": machine.total_supply,
                    },
                }
            ]
        return []
