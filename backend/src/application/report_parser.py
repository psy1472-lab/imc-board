from __future__ import annotations

from datetime import date, time

from domain.day_type import resolve_day_type
from domain.entities import Anomaly, ParsedReport
from domain.format_profile import FormatProfile
from infrastructure.pdf.extractors.daily_kpi import DailyKpiExtractor
from infrastructure.pdf.extractors.operations import (
    QuotaExchangeExtractor,
    SafetyCheckExtractor,
    SortingMachineExtractor,
    TransportExtractor,
)
from infrastructure.pdf.format_detector import ReportFormatDetector
from infrastructure.pdf.reader import PdfReader
from infrastructure.validator import DataValidator


class ReportParser:
    def __init__(self) -> None:
        self.reader = PdfReader()
        self.format_detector = ReportFormatDetector()
        self.daily_extractor = DailyKpiExtractor()
        self.quota_extractor = QuotaExchangeExtractor()
        self.transport_extractor = TransportExtractor()
        self.sorting_extractor = SortingMachineExtractor()
        self.safety_extractor = SafetyCheckExtractor()
        self.validator = DataValidator()

    def parse(self, path: str) -> ParsedReport:
        document = self.reader.read(path)
        profile = self.format_detector.detect_profile(document)
        report_date, center_name, summary = self.daily_extractor.extract(document)
        hourly, staffing = self.daily_extractor.extract_hourly(document, report_date, profile=profile)

        quota = None
        transport = []
        safety_categories = []
        safety_incidents = []

        if "quota" in profile.sections_available:
            quota = self.quota_extractor.extract(document, report_date)
        if "transport" in profile.sections_available:
            transport = self.transport_extractor.extract(document, report_date)
        if "safety" in profile.sections_available:
            safety_categories, safety_incidents = self.safety_extractor.extract(document, report_date)

        sorting = self.sorting_extractor.extract(document, report_date)

        if sorting and sorting.ips_rate is not None:
            summary.ips_rate = sorting.ips_rate

        summary.last_operation_time = self._derive_last_operation_time(hourly)

        day_type = resolve_day_type(report_date)

        report = ParsedReport(
            report_date=report_date,
            center_name=center_name,
            report_format=profile.name,
            day_type=day_type,
            daily_summary=summary,
            hourly_throughput=hourly,
            staffing=staffing,
            quota_exchange=quota,
            transport_offices=transport,
            sorting_machine=sorting,
            safety_categories=safety_categories,
            safety_incidents=safety_incidents,
            anomalies=self._build_anomalies(
                report_date, summary, quota, transport, sorting, safety_incidents, profile
            ),
        )
        report.validation_logs = self.validator.validate(report)
        return report

    def _derive_last_operation_time(self, hourly) -> time | None:
        active = [item for item in hourly if (item.total_volume or 0) > 0]
        if not active:
            return None
        last_slot = active[-1].hour_slot
        hour = int(last_slot) if last_slot != "~18" else 18
        return time(hour=hour, minute=40)

    def _build_anomalies(
        self,
        report_date: date,
        summary,
        quota,
        offices,
        sorting,
        safety_incidents,
        profile: FormatProfile,
    ) -> list[Anomaly]:
        from domain.transport_quota import (
            is_arrival_after_23,
            office_count_volume_text,
            quota_overage,
        )

        anomalies: list[Anomaly] = []

        if (summary.remaining_volume or 0) == 0:
            anomalies.append(
                Anomaly(report_date, "volume", "NORMAL", "잔량 없음, 정상 소통 완료")
            )
        else:
            anomalies.append(
                Anomaly(
                    report_date,
                    "volume",
                    "WARNING",
                    f"잔량 {summary.remaining_volume}개 발생",
                )
            )

        if profile.is_compact:
            anomalies.append(
                Anomaly(
                    report_date,
                    "report",
                    "NORMAL",
                    "주말·공휴일 축약형 보고서",
                )
            )

        overage_offices = [
            office
            for office in offices
            if (quota_overage(office.vehicles_actual, office.vehicles_standard) or 0) > 0
        ]
        delayed_offices = [
            office
            for office in offices
            if is_arrival_after_23(
                office.last_arrival_time,
                volume=office.volume,
                vehicles_actual=office.vehicles_actual,
            )
        ]
        overage_volume = sum(office.volume or 0 for office in overage_offices)
        delayed_volume = sum(office.volume or 0 for office in delayed_offices)
        anomalies.append(
            Anomaly(
                report_date,
                "transport",
                "WARNING" if overage_offices else "NORMAL",
                office_count_volume_text("쿼터 초과 집중국", len(overage_offices), overage_volume),
            )
        )
        anomalies.append(
            Anomaly(
                report_date,
                "transport",
                "WARNING" if delayed_offices else "NORMAL",
                office_count_volume_text("지연(23시초과) 집중국", len(delayed_offices), delayed_volume),
            )
        )

        if sorting and sorting.ips_rate is not None:
            if sorting.ips_rate >= 97:
                anomalies.append(
                    Anomaly(
                        report_date,
                        "equipment",
                        "NORMAL",
                        f"구분기 IPS 정상 ({sorting.ips_rate}% > 목표 97%)",
                    )
                )
            else:
                anomalies.append(
                    Anomaly(
                        report_date,
                        "equipment",
                        "WARNING",
                        f"구분기 IPS 주의 ({sorting.ips_rate}%)",
                    )
                )

        if safety_incidents:
            anomalies.append(
                Anomaly(
                    report_date,
                    "safety",
                    "WARNING",
                    f"안전사고 {len(safety_incidents)}건 발생",
                )
            )
        elif not profile.is_compact:
            anomalies.append(
                Anomaly(report_date, "safety", "NORMAL", "안전사고 없음")
            )
        return anomalies[:5]
