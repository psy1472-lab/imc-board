from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

from application.volume_forecast_service import VolumeForecastService
from domain.volume_forecast import (
    build_forecast_accuracy_text,
    build_volume_forecast_text,
    estimate_staff_for_volume,
)
from domain.volume_ml_forecast import build_ml_volume_forecast_text
from infrastructure.db.sqlite_repository import SqliteRepository

STATUS_LABELS = {
    "NORMAL": "적정",
    "CAUTION": "관심",
    "WARNING": "관리필요",
    "CRITICAL": "위험",
    "UNKNOWN": "미확인",
}

STATUS_RANK = {"CRITICAL": 0, "WARNING": 1, "CAUTION": 2, "UNKNOWN": 3, "NORMAL": 4}

JUDGMENT_PHRASES = {
    "NORMAL": "현재 수준은 적정 범위로 보입니다.",
    "CAUTION": "추세 모니터링이 필요할 수 있습니다.",
    "WARNING": "관리·대응 검토가 필요할 수 있습니다.",
    "CRITICAL": "즉각적인 점검이 필요할 수 있습니다.",
    "UNKNOWN": "판단에 필요한 데이터가 부족합니다.",
}

BRIEFING_COMPARE_SPECS = (
    ("prevDay", "전일"),
    ("sameWeekday", "동일 요일 평균"),
    ("avg7d", "최근 7업무일 평균"),
)

COVERED_ANOMALY_CATEGORIES = frozenset({"volume", "transport", "equipment", "safety"})


class BriefingService:
    def __init__(self, repository: SqliteRepository, *, model_cache_path: str | None = None) -> None:
        self.repository = repository
        self.volume_forecast_service = VolumeForecastService(
            repository,
            model_cache_path=model_cache_path,
        )

    def generate(
        self,
        report_date: str,
        compare_basis: str = "prev_day",
        *,
        sections: str = "all",
    ) -> dict:
        if sections == "forecast":
            return self._generate_forecast_section(report_date)

        internal_compare = "7d_avg"
        summary = self.repository.get_dashboard_summary(report_date, internal_compare)
        if not summary:
            return {}

        with ThreadPoolExecutor(max_workers=6) as pool:
            volume_future = pool.submit(self.repository.get_volume_analysis, report_date)
            staffing_future = pool.submit(self.repository.get_staffing_analysis, report_date)
            transport_future = pool.submit(self.repository.get_transport_analysis, report_date)
            equipment_future = pool.submit(self.repository.get_equipment_analysis, report_date)
            safety_future = pool.submit(self.repository.get_safety_analysis, report_date)
            hourly_future = pool.submit(self.repository.get_hourly_volume_pattern, report_date)
            volume = volume_future.result()
            staffing = staffing_future.result()
            transport = transport_future.result()
            equipment = equipment_future.result()
            safety = safety_future.result()
            hourly_pattern = hourly_future.result()

        anomalies = safety.get("anomalies", [])
        quota_overages = transport.get("quotaOverages", [])

        major_changes = self._build_major_changes(volume, staffing, equipment)
        highlights = self._build_highlights(anomalies, quota_overages, safety.get("summary", {}))

        payload = {
            "meta": {
                "reportDate": report_date,
                "centerName": summary.get("meta", {}).get("centerName"),
                "compareBasis": "current_day",
                "compareLabel": "당일",
                "communicationStatus": summary.get("meta", {}).get("communicationStatusLabel"),
                "generatedAt": datetime.utcnow().isoformat(),
                "source": "rule_based",
            },
            "sections": {
                "todayOperation": {
                    "title": "오늘의 운영상황",
                    "items": self._build_today_operation_items(volume, anomalies),
                },
                "majorChanges": {
                    "title": "주요 변화",
                    "items": major_changes,
                },
                "staffing": self._build_staffing_section(staffing),
                "transport": self._build_transport_section(transport, anomalies),
                "equipment": self._build_equipment_section(equipment, anomalies),
                "safety": self._build_safety_section(safety, anomalies),
            },
            "highlights": highlights,
            "disclaimer": (
                "본 브리핑은 PDF 보고서 기반 데이터를 규칙으로 요약·해석한 참고 자료입니다. "
                "최종 운영 판단은 담당자 확인이 필요합니다."
            ),
        }

        if sections in {"all", "forecast"}:
            forecast_ctx = self.repository.get_volume_forecast_context(report_date)
            ml_rows = self.volume_forecast_service.ml_service.load_rows(report_date)
            report_dates = self.repository.list_report_dates()
            payload["tomorrowOutlook"] = {
                "title": "내일 전망",
                "items": self._build_tomorrow_outlook(
                    report_date,
                    volume,
                    staffing,
                    transport,
                    equipment,
                    safety,
                    hourly_pattern,
                    forecast_ctx=forecast_ctx,
                    ml_rows=ml_rows,
                    report_dates=report_dates,
                ),
            }
        elif sections == "core":
            payload["tomorrowOutlook"] = {"title": "내일 전망", "items": []}

        return payload

    def _generate_forecast_section(self, report_date: str) -> dict:
        summary = self.repository.get_dashboard_summary(report_date, "7d_avg")
        if not summary:
            return {}
        volume = self.repository.get_volume_analysis(report_date)
        staffing = self.repository.get_staffing_analysis(report_date)
        transport = self.repository.get_transport_analysis(report_date)
        equipment = self.repository.get_equipment_analysis(report_date)
        safety = self.repository.get_safety_analysis(report_date)
        hourly_pattern = self.repository.get_hourly_volume_pattern(report_date)
        forecast_ctx = self.repository.get_volume_forecast_context(report_date)
        ml_rows = self.volume_forecast_service.ml_service.load_rows(report_date)
        report_dates = self.repository.list_report_dates()
        return {
            "meta": {
                "reportDate": report_date,
                "generatedAt": datetime.utcnow().isoformat(),
                "source": "rule_based",
            },
            "tomorrowOutlook": {
                "title": "내일 전망",
                "items": self._build_tomorrow_outlook(
                    report_date,
                    volume,
                    staffing,
                    transport,
                    equipment,
                    safety,
                    hourly_pattern,
                    forecast_ctx=forecast_ctx,
                    ml_rows=ml_rows,
                    report_dates=report_dates,
                ),
            },
        }

    def _build_today_operation_items(self, volume: dict, anomalies: list[dict]) -> list[dict]:
        volume_summary = volume.get("summary", {})
        return [
            {
                "label": "총 처리물량",
                "value": self._format_thousand(volume_summary.get("totalVolume")),
                "unit": "천개",
            },
            {
                "label": "발송",
                "value": self._format_thousand(volume_summary.get("dispatchVolume")),
                "unit": "천개",
            },
            {
                "label": "도착",
                "value": self._format_thousand(volume_summary.get("arrivalVolume")),
                "unit": "천개",
            },
            {
                "label": "잔량",
                "value": self._format_thousand(volume_summary.get("remainingVolume")),
                "unit": "천개",
                **(
                    {"text": remaining_detail}
                    if (remaining_detail := self._join_messages(
                        self._anomaly_category_messages(anomalies, "volume")
                    ))
                    else {}
                ),
            },
            {
                "label": "전국대비 처리율",
                "value": volume_summary.get("processingRate"),
                "unit": "%",
            },
        ]

    def _build_staffing_section(
        self,
        staffing: dict,
    ) -> dict:
        summary = staffing.get("summary", {})
        benchmarks = staffing.get("benchmarks", {})

        productivity_assessment = self._assess_trend_metric_multi(
            summary.get("productivity"),
            benchmarks,
            "productivity",
            higher_is_better=True,
            moderate_drop=5,
            severe_drop=10,
        )
        avg_staff_assessment = self._assess_trend_metric_multi(
            summary.get("avgStaff"),
            benchmarks,
            "avgStaff",
            higher_is_better=None,
            moderate_drop=8,
            severe_drop=15,
        )
        peak_staff_assessment = self._assess_trend_metric_multi(
            summary.get("peakStaff"),
            benchmarks,
            "peakStaff",
            higher_is_better=None,
            moderate_drop=10,
            severe_drop=20,
        )
        bottleneck_assessment = self._assess_bottleneck(summary, benchmarks)

        items = [
            {
                "label": "인시당 처리량",
                "value": summary.get("productivity"),
                "unit": "개",
                **productivity_assessment,
            },
            {
                "label": "평균 실근무인력",
                "value": summary.get("avgStaff"),
                "unit": "명",
                **avg_staff_assessment,
            },
            {
                "label": "피크 실근무인력",
                "value": summary.get("peakStaff"),
                "unit": "명",
                **peak_staff_assessment,
            },
            {
                "label": "병목 가능 시간대",
                "text": self._bottleneck_text(summary),
                **bottleneck_assessment,
            },
        ]

        statuses = [item["status"] for item in items]
        overall_status = self._worst_status(*statuses)
        gaps = [
            "결위율·정원·단기근로자·연장근무 (PDF 미추출)",
            "물량 대비 적정인력 산출 미제공",
        ]
        if summary.get("productivity") is None:
            gaps.insert(0, "인시당 처리량 원본 미추출")
        assessment = self._section_assessment(
            overall_status,
            "인력",
            productivity_assessment,
            avg_staff_assessment,
            bottleneck_assessment,
        )
        return {
            "title": "인력",
            "overallStatus": overall_status,
            "overallLabel": STATUS_LABELS[overall_status],
            "assessment": assessment,
            "gaps": gaps,
            "items": items,
        }

    def _build_transport_section(self, transport: dict, anomalies: list[dict]) -> dict:
        summary = transport.get("summary", {})
        benchmarks = transport.get("benchmarks", {})

        quarter_assessment = self._assess_trend_metric_multi(
            summary.get("quarterComplianceRate"),
            benchmarks,
            "quarterComplianceRate",
            higher_is_better=True,
            moderate_drop=2,
            severe_drop=5,
            absolute_warning=95,
            absolute_critical=90,
        )
        exchange_assessment = self._assess_trend_metric_multi(
            summary.get("exchangeComplianceRate"),
            benchmarks,
            "exchangeComplianceRate",
            higher_is_better=True,
            moderate_drop=2,
            severe_drop=5,
            absolute_warning=95,
            absolute_critical=90,
        )
        overage_count = summary.get("overageOfficeCount") or 0
        overage_volume = int(summary.get("overageOfficeVolume") or 0)
        overage_assessment = self._assess_count_metric(
            overage_count,
            warning_at=1,
            critical_at=15,
            label="쿼터 초과 집중국",
            detail=self._transport_overage_detail(transport),
        )
        remaining = summary.get("exchangeRemaining")
        remaining_assessment = self._assess_remaining(remaining)
        delayed_count = summary.get("delayedOfficeCount") or 0
        delayed_volume = int(summary.get("delayedOfficeVolume") or 0)
        delayed_assessment = self._assess_count_metric(
            delayed_count,
            warning_at=1,
            critical_at=15,
            label="지연(23시초과) 집중국",
            detail=f"물량 {delayed_volume:,}개" if delayed_count else None,
        )

        items = [
            {
                "label": "쿼터 준수율",
                "value": summary.get("quarterComplianceRate"),
                "unit": "%",
                **self._merge_item_text(
                    quarter_assessment,
                    self._quota_text(summary),
                ),
            },
            {
                "label": "교환 준수율",
                "value": summary.get("exchangeComplianceRate"),
                "unit": "%",
                **exchange_assessment,
            },
            {
                "label": "쿼터 초과 집중국",
                "value": overage_count,
                "unit": "곳",
                **self._merge_item_text(
                    overage_assessment,
                    f"물량 {overage_volume:,}개" if overage_count else None,
                ),
            },
            {
                "label": "지연(23시초과) 집중국",
                "value": delayed_count,
                "unit": "곳",
                **delayed_assessment,
            },
            {
                "label": "교환 잔량",
                "text": "없음" if remaining == 0 else str(remaining),
                **remaining_assessment,
            },
        ]

        statuses = [item["status"] for item in items]
        overall_status = self._worst_status(*statuses)
        gaps = [
            "최종 발송·도착시간 (PDF 미추출)",
            "제주 D+1/D+2 운송편 (PDF 미추출)",
            "상습 지연 노선 분석 미제공",
        ]
        if not transport.get("offices"):
            gaps.insert(0, "집중국별 상세 운송 데이터 없음")
        assessment = self._section_assessment(
            overall_status,
            "운송",
            quarter_assessment,
            exchange_assessment,
            overage_assessment,
            delayed_assessment,
        )
        return {
            "title": "운송",
            "overallStatus": overall_status,
            "overallLabel": STATUS_LABELS[overall_status],
            "assessment": assessment,
            "gaps": gaps,
            "items": items,
        }

    def _build_equipment_section(self, equipment: dict, anomalies: list[dict]) -> dict:
        summary = equipment.get("summary", {})
        benchmarks = equipment.get("benchmarks", {})
        ips_target = summary.get("ipsTarget", 97.0)

        ips_assessment = self._assess_ips(summary.get("ipsRate"), ips_target, benchmarks)
        ips_item = self._merge_item_text(
            ips_assessment,
            self._ips_text(summary),
            self._join_messages(self._anomaly_category_messages(anomalies, "equipment")),
        )
        sorting_assessment = self._assess_trend_metric_multi(
            summary.get("sortingRate"),
            benchmarks,
            "sortingRate",
            higher_is_better=True,
            moderate_drop=1,
            severe_drop=3,
            absolute_warning=95,
            absolute_critical=90,
        )
        reject_assessment = self._assess_trend_metric_multi(
            summary.get("rejectRate"),
            benchmarks,
            "rejectRate",
            higher_is_better=False,
            moderate_drop=2,
            severe_drop=5,
            absolute_warning=5,
            absolute_critical=10,
            invert_absolute=True,
        )
        unread_assessment = self._assess_trend_metric_multi(
            summary.get("unreadRate"),
            benchmarks,
            "unreadRate",
            higher_is_better=False,
            moderate_drop=2,
            severe_drop=5,
            absolute_warning=5,
            absolute_critical=10,
            invert_absolute=True,
        )
        shortcut_assessment = self._assess_trend_metric_multi(
            summary.get("shortcutRate"),
            benchmarks,
            "shortcutRate",
            higher_is_better=False,
            moderate_drop=3,
            severe_drop=8,
            absolute_warning=10,
            absolute_critical=15,
            invert_absolute=True,
        )

        items = [
            {
                "label": "IPS",
                "value": summary.get("ipsRate"),
                "unit": "%",
                **ips_item,
            },
            {
                "label": "구분율",
                "value": summary.get("sortingRate"),
                "unit": "%",
                **sorting_assessment,
            },
            {
                "label": "Reject율",
                "value": summary.get("rejectRate"),
                "unit": "%",
                **reject_assessment,
            },
            {
                "label": "미판독율",
                "value": summary.get("unreadRate"),
                "unit": "%",
                **unread_assessment,
            },
            {
                "label": "숏컷 점유율",
                "value": summary.get("shortcutRate"),
                "unit": "%",
                **shortcut_assessment,
            },
        ]

        statuses = [item["status"] for item in items if item.get("value") is not None]
        overall_status = self._worst_status(*(statuses or ["UNKNOWN"]))
        gaps = [
            "다중판독·코드 미등록 (PDF 미추출)",
            "시간당 피크 처리량 추세 분석 미제공",
        ]
        if summary.get("ipsRate") is None:
            gaps.insert(0, "설비 가동 데이터 미수집")
        assessment = self._section_assessment(
            overall_status,
            "설비",
            ips_assessment,
            sorting_assessment,
            reject_assessment,
        )
        return {
            "title": "설비",
            "overallStatus": overall_status,
            "overallLabel": STATUS_LABELS[overall_status],
            "assessment": assessment,
            "gaps": gaps,
            "items": items,
        }

    def _build_safety_section(self, safety: dict, anomalies: list[dict]) -> dict:
        summary = safety.get("summary", {})
        benchmarks = safety.get("benchmarks", {})
        incident_count = summary.get("incidentCount", 0) or 0

        pass_assessment = self._assess_trend_metric_multi(
            summary.get("safetyPassRate"),
            benchmarks,
            "safetyPassRate",
            higher_is_better=True,
            moderate_drop=1,
            severe_drop=5,
            absolute_warning=100,
            absolute_critical=95,
        )
        incident_assessment = self._assess_count_metric(
            incident_count,
            warning_at=1,
            critical_at=1,
            label="재해",
            critical_is_incident=True,
            detail=self._join_messages(self._anomaly_category_messages(anomalies, "safety")),
        )
        overall_status = summary.get("overallStatus", "NORMAL")
        overall_label = summary.get("overallLabel", STATUS_LABELS.get(overall_status, "미확인"))
        uncovered_messages = self._uncovered_anomaly_messages(anomalies)

        items = [
            {
                "label": "안전점검 양호율",
                "value": summary.get("safetyPassRate"),
                "unit": "%",
                **pass_assessment,
            },
            {
                "label": "재해",
                "value": incident_count,
                "unit": "건",
                **incident_assessment,
            },
        ]
        if uncovered_messages:
            uncovered_detail = self._join_messages(uncovered_messages)
            items.append(
                {
                    "label": "기타 이상징후",
                    "value": len(uncovered_messages),
                    "unit": "건",
                    **self._assess_count_metric(
                        len(uncovered_messages),
                        warning_at=1,
                        critical_at=3,
                        label="기타 이상징후",
                        detail=uncovered_detail,
                    ),
                }
            )
        items.append(
            {
                "label": "종합 상태",
                "text": overall_label,
                "status": overall_status,
                "statusLabel": STATUS_LABELS.get(overall_status, overall_label),
                "assessment": self._safety_overall_assessment(summary, benchmarks, anomalies),
            }
        )

        anomaly_assessment = next(
            (item for item in items if item["label"] == "기타 이상징후"),
            {"status": "NORMAL"},
        )

        statuses = [item["status"] for item in items]
        merged_status = self._worst_status(overall_status, *statuses)
        gaps = [
            "반복 지적사항·불량판정 상세 (PDF 미추출)",
            "점검 카테고리별 조치사항 추적 미제공",
        ]
        if not safety.get("safety", {}).get("categories"):
            gaps.insert(0, "안전점검 카테고리 데이터 없음")
        assessment = self._section_assessment(
            merged_status,
            "안전",
            pass_assessment,
            incident_assessment,
            anomaly_assessment,
        )
        return {
            "title": "안전",
            "overallStatus": merged_status,
            "overallLabel": STATUS_LABELS.get(merged_status, overall_label),
            "assessment": assessment,
            "gaps": gaps,
            "items": items,
        }

    def _is_warning_anomaly(self, anomaly: dict) -> bool:
        return anomaly.get("severity") in {"WARNING", "CRITICAL"}

    def _anomaly_category_messages(self, anomalies: list[dict], category: str) -> list[str]:
        return [
            anomaly["message"]
            for anomaly in anomalies
            if self._is_warning_anomaly(anomaly)
            and anomaly.get("category") == category
            and anomaly.get("message")
        ]

    def _uncovered_anomaly_messages(self, anomalies: list[dict]) -> list[str]:
        return [
            anomaly["message"]
            for anomaly in anomalies
            if self._is_warning_anomaly(anomaly)
            and anomaly.get("category") not in COVERED_ANOMALY_CATEGORIES
            and anomaly.get("message")
        ]

    def _join_messages(self, messages: list[str]) -> str | None:
        unique_messages = list(dict.fromkeys(messages))
        return " · ".join(unique_messages) if unique_messages else None

    def _merge_item_text(self, assessment: dict, *extra_texts: str | None) -> dict:
        merged = dict(assessment)
        text_parts = [part for part in [merged.get("text"), *extra_texts] if part]
        unique_parts = list(dict.fromkeys(text_parts))
        if unique_parts:
            merged["text"] = " · ".join(unique_parts)
        return merged

    def _transport_overage_detail(self, transport: dict) -> str | None:
        parts: list[str] = []
        overages = transport.get("quotaOverages", [])
        for office in overages[:4]:
            name = office.get("office")
            if name:
                parts.append(name)
        extra_count = len(overages) - 4
        if extra_count > 0:
            parts.append(f"외 {extra_count}곳")
        return self._join_messages(parts)

    def _benchmark_for(self, analysis: dict, compare_basis: str) -> dict:
        key_map = {
            "prev_day": "prevDay",
            "7d_avg": "avg7d",
            "30d_avg": "avg30d",
            "same_weekday": "sameWeekday",
        }
        return analysis.get("benchmarks", {}).get(key_map.get(compare_basis, "prevDay"), {}) or {}

    def _percent_delta(self, current: float | int | None, baseline: float | int | None) -> tuple[float | None, str | None]:
        if current is None or baseline in (None, 0):
            return None, None
        percent = ((current - baseline) / baseline) * 100
        if percent > 0.5:
            trend = "UP"
        elif percent < -0.5:
            trend = "DOWN"
        else:
            trend = "FLAT"
        return round(percent, 1), trend

    def _worst_status(self, *statuses: str) -> str:
        valid = [status for status in statuses if status in STATUS_RANK]
        if not valid:
            return "UNKNOWN"
        return min(valid, key=lambda status: STATUS_RANK[status])

    def _format_multi_compare_sentence(
        self,
        current: float | int | None,
        benchmarks: dict,
        metric_key: str,
    ) -> str:
        if current is None:
            return "비교 가능한 당일 데이터가 없습니다."

        segments: list[str] = []
        for bench_key, label in BRIEFING_COMPARE_SPECS:
            baseline = (benchmarks.get(bench_key) or {}).get(metric_key)
            percent, trend = self._percent_delta(current, baseline)
            if percent is None:
                continue
            if trend == "FLAT":
                segments.append(f"{label} 대비 유사한 수준")
            else:
                direction = "증가" if trend == "UP" else "감소"
                segments.append(f"{label} 대비 {abs(percent):.1f}% {direction}")

        if not segments:
            return "비교 기준이 충분하지 않습니다."

        if len(segments) == 1:
            suffix = "입니다." if "유사" in segments[0] else "했습니다."
            return segments[0] + suffix
        return ", ".join(segments[:-1]) + ", " + segments[-1] + "했습니다."

    def _assess_trend_metric_multi(
        self,
        current: float | int | None,
        benchmarks: dict,
        metric_key: str,
        **kwargs,
    ) -> dict:
        primary_baseline = (benchmarks.get("avg7d") or {}).get(metric_key)
        assessment = self._assess_trend_metric(
            current,
            primary_baseline,
            "최근 7업무일 평균",
            **kwargs,
        )
        compare_sentence = self._format_multi_compare_sentence(current, benchmarks, metric_key)
        if compare_sentence not in {
            "비교 가능한 당일 데이터가 없습니다.",
            "비교 기준이 충분하지 않습니다.",
        }:
            assessment["text"] = compare_sentence
        assessment["assessment"] = JUDGMENT_PHRASES[assessment["status"]]
        return assessment

    def _assess_trend_metric(
        self,
        current: float | int | None,
        baseline: float | int | None,
        compare_label: str,
        *,
        higher_is_better: bool | None = True,
        moderate_drop: float = 5,
        severe_drop: float = 10,
        absolute_warning: float | None = None,
        absolute_critical: float | None = None,
        invert_absolute: bool = False,
    ) -> dict:
        if current is None:
            return self._empty_assessment()

        status = "NORMAL"
        parts: list[str] = []
        percent, trend = self._percent_delta(current, baseline)

        if percent is not None and trend is not None:
            direction = "높" if percent > 0 else "낮"
            if trend != "FLAT":
                parts.append(f"{compare_label} 대비 {abs(percent):.1f}% {direction}음")
            else:
                parts.append(f"{compare_label} 대비 유사한 수준")

            if higher_is_better is True:
                if percent <= -severe_drop:
                    status = self._worst_status(status, "WARNING")
                elif percent <= -moderate_drop:
                    status = self._worst_status(status, "CAUTION")
                elif percent >= severe_drop * 1.5:
                    status = self._worst_status(status, "CAUTION")
            elif higher_is_better is False:
                if percent >= severe_drop:
                    status = self._worst_status(status, "WARNING")
                elif percent >= moderate_drop:
                    status = self._worst_status(status, "CAUTION")
            elif abs(percent) >= severe_drop:
                status = self._worst_status(status, "CAUTION")

        if absolute_warning is not None:
            if invert_absolute:
                if absolute_critical is not None and current >= absolute_critical:
                    status = self._worst_status(status, "CRITICAL")
                elif current >= absolute_warning:
                    status = self._worst_status(status, "WARNING")
            else:
                if absolute_critical is not None and current < absolute_critical:
                    status = self._worst_status(status, "CRITICAL")
                elif current < absolute_warning:
                    status = self._worst_status(status, "WARNING")

        parts.append(JUDGMENT_PHRASES[status])
        return {
            "status": status,
            "statusLabel": STATUS_LABELS[status],
            "assessment": " ".join(parts) + ".",
            "trend": trend,
            "trendPercent": percent,
        }

    def _assess_ips(
        self,
        current: float | None,
        target: float,
        benchmarks: dict,
    ) -> dict:
        assessment = self._assess_trend_metric_multi(
            current,
            benchmarks,
            "ipsRate",
            higher_is_better=True,
            moderate_drop=0.5,
            severe_drop=1.5,
        )
        if current is None:
            return assessment
        if current < target - 2:
            assessment["status"] = self._worst_status(assessment["status"], "CRITICAL")
        elif current < target:
            assessment["status"] = self._worst_status(assessment["status"], "WARNING")
        assessment["statusLabel"] = STATUS_LABELS[assessment["status"]]
        compare_sentence = assessment.get("text")
        if current < target:
            prefix = f"목표 {target}% 대비 {target - current:.2f}%p 낮음."
            assessment["text"] = " · ".join(filter(None, [prefix, compare_sentence]))
        elif compare_sentence:
            assessment["text"] = f"목표 {target}% 이상 유지 · {compare_sentence}"
        else:
            assessment["text"] = f"목표 {target}% 이상 유지"
        assessment["assessment"] = JUDGMENT_PHRASES[assessment["status"]]
        return assessment

    def _assess_count_metric(
        self,
        count: int,
        *,
        warning_at: int,
        critical_at: int,
        label: str,
        critical_is_incident: bool = False,
        detail: str | None = None,
    ) -> dict:
        if critical_is_incident and count > 0:
            status = "CRITICAL"
            assessment = JUDGMENT_PHRASES[status]
        elif count >= critical_at:
            status = "CRITICAL"
            assessment = JUDGMENT_PHRASES[status]
        elif count >= warning_at:
            status = "WARNING"
            assessment = JUDGMENT_PHRASES[status]
        else:
            status = "NORMAL"
            assessment = JUDGMENT_PHRASES[status]
        return {
            "status": status,
            "statusLabel": STATUS_LABELS[status],
            "text": detail,
            "assessment": assessment,
            "trend": None,
            "trendPercent": None,
        }

    def _assess_remaining(self, remaining: int | None) -> dict:
        if remaining is None:
            return self._empty_assessment()
        if remaining > 0:
            return {
                "status": "WARNING",
                "statusLabel": STATUS_LABELS["WARNING"],
                "assessment": f"교환 잔량 {remaining}건 잔존. 후속 처리 확인이 필요할 수 있습니다.",
                "trend": None,
                "trendPercent": None,
            }
        return {
            "status": "NORMAL",
            "statusLabel": STATUS_LABELS["NORMAL"],
            "assessment": "교환 잔량 없음. 현재 수준은 적정 범위로 보입니다.",
            "trend": None,
            "trendPercent": None,
        }

    def _assess_bottleneck(self, summary: dict, benchmarks: dict) -> dict:
        peak_hour = summary.get("peakHour")
        peak_volume = summary.get("peakHourVolume")
        total_volume = summary.get("totalVolume")
        if not peak_hour:
            return self._empty_assessment("피크 시간대 데이터가 충분하지 않습니다.")

        status = "NORMAL"
        parts = [f"{peak_hour}에 물량이 가장 집중되었습니다."]
        if peak_volume is not None and total_volume:
            share = (peak_volume / total_volume) * 100 if total_volume else 0
            if share >= 25:
                status = "WARNING"
                parts.append(
                    f"일일 물량의 {share:.1f}%가 해당 시간대에 집중되어 인력 집중 배치 검토가 필요할 수 있습니다."
                )
            elif share >= 18:
                status = "CAUTION"
                parts.append(f"일일 물량의 {share:.1f}%가 집중되어 모니터링이 필요할 수 있습니다.")
            else:
                parts.append(JUDGMENT_PHRASES[status])
        else:
            parts.append(JUDGMENT_PHRASES[status])

        avg_staff = summary.get("avgStaff")
        benchmark_staff = benchmarks.get("avg7d", {}).get("avgStaff")
        if avg_staff is not None and benchmark_staff is not None:
            percent, trend = self._percent_delta(avg_staff, benchmark_staff)
            if trend == "DOWN" and percent is not None and percent <= -10:
                status = self._worst_status(status, "CAUTION")
                parts.append(f"평균 실근무인력은 최근 7업무일 평균 대비 {abs(percent):.1f}% 낮습니다.")

        return {
            "status": status,
            "statusLabel": STATUS_LABELS[status],
            "assessment": " ".join(parts),
            "trend": None,
            "trendPercent": None,
        }

    def _safety_overall_assessment(self, summary: dict, benchmarks: dict, anomalies: list[dict]) -> str:
        incident_count = summary.get("incidentCount", 0) or 0
        pass_rate = summary.get("safetyPassRate")
        parts: list[str] = []
        if incident_count > 0:
            parts.append(f"재해 {incident_count}건으로 즉각 후속 관리가 필요합니다.")
        uncovered = self._uncovered_anomaly_messages(anomalies)
        if uncovered:
            parts.append(self._join_messages(uncovered) or "")
        if pass_rate is not None:
            compare_sentence = self._format_multi_compare_sentence(pass_rate, benchmarks, "safetyPassRate")
            if compare_sentence not in {
                "비교 가능한 당일 데이터가 없습니다.",
                "비교 기준이 충분하지 않습니다.",
            }:
                parts.append(compare_sentence)
        if not parts:
            return "안전 지표는 전반적으로 안정적인 수준으로 보입니다."
        return " ".join(parts)

    def _section_assessment(self, overall_status: str, domain: str, *metric_assessments: dict) -> str:
        if overall_status == "NORMAL":
            return f"{domain} 운영은 전반적으로 적정 수준으로 보입니다."
        status_label = STATUS_LABELS.get(overall_status, "주의")
        return f"{domain} 영역에 {status_label} 신호가 있습니다. 아래 항목을 확인하세요."

    def _empty_assessment(self, message: str | None = None) -> dict:
        return {
            "status": "UNKNOWN",
            "statusLabel": STATUS_LABELS["UNKNOWN"],
            "assessment": message or JUDGMENT_PHRASES["UNKNOWN"],
            "trend": None,
            "trendPercent": None,
        }

    def _format_thousand(self, value: float | int | None) -> str | None:
        if value is None:
            return None
        return f"{value:,.1f}".rstrip("0").rstrip(".")

    def _build_major_changes(self, volume: dict, staffing: dict, equipment: dict) -> list[dict]:
        metric_defs = [
            ("총 처리물량", volume.get("summary", {}).get("totalVolume"), volume.get("benchmarks", {}), "totalVolume"),
            ("발송물량", volume.get("summary", {}).get("dispatchVolume"), volume.get("benchmarks", {}), "dispatchVolume"),
            ("도착물량", volume.get("summary", {}).get("arrivalVolume"), volume.get("benchmarks", {}), "arrivalVolume"),
            ("잔량", volume.get("summary", {}).get("remainingVolume"), volume.get("benchmarks", {}), "remainingVolume"),
            ("인시당 처리량", staffing.get("summary", {}).get("productivity"), staffing.get("benchmarks", {}), "productivity"),
            ("IPS", equipment.get("summary", {}).get("ipsRate"), equipment.get("benchmarks", {}), "ipsRate"),
        ]
        items: list[dict] = []
        for label, current, benchmarks, metric_key in metric_defs:
            if current is None:
                continue
            text = self._format_multi_compare_sentence(current, benchmarks, metric_key)
            if text in {"비교 가능한 당일 데이터가 없습니다.", "비교 기준이 충분하지 않습니다."}:
                continue
            percent, trend = self._percent_delta(current, (benchmarks.get("avg7d") or {}).get(metric_key))
            items.append(
                {
                    "label": label,
                    "text": text,
                    "trend": trend,
                    "percent": percent,
                }
            )
        return items

    def _bottleneck_text(self, staffing_summary: dict) -> str:
        peak_hour = staffing_summary.get("peakHour")
        peak_volume = staffing_summary.get("peakHourVolume")
        if not peak_hour:
            return "피크 시간대 데이터가 충분하지 않습니다."
        volume_text = f", 처리물량 {peak_volume}천" if peak_volume is not None else ""
        return f"{peak_hour} 물량이 가장 집중되었습니다{volume_text}."

    def _quota_text(self, transport_summary: dict) -> str | None:
        actual = transport_summary.get("quarterActual")
        standard = transport_summary.get("quarterStandard")
        if actual is None or standard is None:
            return None
        if actual > standard:
            return f"쿼터 운송 {actual}/{standard}대입니다."
        return "쿼터 기준 범위 내로 보입니다."

    def _ips_text(self, equipment_summary: dict) -> str | None:
        ips = equipment_summary.get("ipsRate")
        target = equipment_summary.get("ipsTarget")
        if ips is None or target is None:
            return None
        if ips >= target:
            return f"목표 {target}% 이상으로 유지되고 있습니다."
        return f"목표 {target}% 대비 낮아 추가 점검이 필요할 수 있습니다."

    def _build_highlights(
        self,
        anomalies: list[dict],
        quota_overages: list[dict],
        safety_summary: dict,
    ) -> list[dict]:
        highlights: list[dict] = []
        severity_rank = {"CRITICAL": 0, "WARNING": 1, "CAUTION": 2, "NORMAL": 3}
        sorted_anomalies = sorted(
            anomalies,
            key=lambda item: severity_rank.get(item.get("severity", "NORMAL"), 9),
        )
        for item in sorted_anomalies:
            if item.get("severity") == "NORMAL":
                continue
            highlights.append(
                {
                    "severity": item.get("severity"),
                    "category": item.get("categoryLabel") or item.get("category"),
                    "message": item.get("message"),
                }
            )
            if len(highlights) >= 5:
                break

        if len(highlights) < 5:
            for office in quota_overages[: 5 - len(highlights)]:
                highlights.append(
                    {
                        "severity": "WARNING",
                        "category": "운송",
                        "message": f"{office.get('office')} 쿼터 초과 (차량 {office.get('vehiclesActual')}/{office.get('vehiclesQuota')})",
                    }
                )

        if not highlights:
            highlights.append(
                {
                    "severity": "NORMAL",
                    "category": "종합",
                    "message": "특이하게 보고된 주요 이상징후가 없습니다.",
                }
            )
        return highlights[:5]

    def _build_tomorrow_outlook(
        self,
        report_date: str,
        volume: dict,
        staffing: dict,
        transport: dict,
        equipment: dict,
        safety: dict,
        hourly_pattern: dict,
        *,
        forecast_ctx: dict,
        ml_rows: list,
        report_dates: list[str],
    ) -> list[dict]:
        items: list[dict] = []
        volume_summary = volume.get("summary", {})
        volume_benchmarks = volume.get("benchmarks", {})

        stored_forecast = self.repository.get_daily_forecast(report_date)
        forecast_outcome = None
        forecast_text = stored_forecast.get("forecastText") if stored_forecast else None

        if forecast_text:
            items.append({"label": "예상 물량", "text": forecast_text})
            forecast_volume = stored_forecast.get("forecastVolume")
        else:
            forecast_outcome = self.volume_forecast_service.predict(
                report_date,
                forecast_ctx=forecast_ctx,
                rows=ml_rows,
                volume=volume,
            )
            if forecast_outcome is not None:
                if forecast_outcome.method.startswith("ml") and forecast_outcome.ml_result is not None:
                    forecast_text = build_ml_volume_forecast_text(forecast_outcome.ml_result)
                else:
                    rule_result = self.volume_forecast_service._predict_rule(
                        report_date,
                        forecast_ctx,
                        volume=volume,
                    )
                    forecast_text = (
                        build_volume_forecast_text(rule_result) + f" [{forecast_outcome.method_label}]"
                        if rule_result is not None
                        else None
                    )
                if forecast_text:
                    items.append({"label": "예상 물량", "text": forecast_text})
            forecast_volume = forecast_outcome.forecast_volume if forecast_outcome else None

        prior_outcome = self.volume_forecast_service.predict_for_target(
            report_date,
            report_dates=report_dates,
        )
        today_volume = volume_summary.get("totalVolume")
        if prior_outcome is not None and today_volume is not None:
            accuracy_text = build_forecast_accuracy_text(
                prior_outcome.forecast_volume,
                today_volume,
                forecast_date=report_date,
            )
            if accuracy_text:
                method_hint = f" ({prior_outcome.method_label})"
                items.append(
                    {
                        "label": "전일 예측 검증",
                        "text": accuracy_text + method_hint,
                    }
                )

        peak_hour = hourly_pattern.get("peakHour")
        sample_days = hourly_pattern.get("sampleDays", 0)
        if peak_hour and sample_days > 0:
            peak_volume = hourly_pattern.get("peakHourVolume")
            volume_text = f"(평균 약 {peak_volume:,.1f}천개)" if peak_volume is not None else ""
            items.append(
                {
                    "label": "피크 시간",
                    "text": (
                        f"최근 {sample_days}업무일 시간대별 평균 기준 {peak_hour} 전후에 "
                        f"물량 집중이 예상됩니다{volume_text}."
                    ),
                }
            )

        avg_staff_7d = staffing.get("benchmarks", {}).get("avg7d", {}).get("avgStaff")
        ref_volume = (
            forecast_ctx.get("sameTypeAvg7d")
            or volume_benchmarks.get("avg7d", {}).get("totalVolume")
        )
        forecast_volume = (
            forecast_volume
            if forecast_volume is not None
            else (forecast_outcome.forecast_volume if forecast_outcome is not None else None)
        )
        suggested_staff = (
            estimate_staff_for_volume(forecast_volume, ref_volume, avg_staff_7d)
            if forecast_volume is not None
            else None
        )
        if suggested_staff is not None:
            items.append(
                {
                    "label": "적정인력 참고",
                    "text": (
                        f"예상 물량과 최근 7업무일 평균 생산성·인력 패턴을 반영하면 "
                        f"실근무인력 약 {suggested_staff}명 배치를 검토할 수 있습니다."
                    ),
                }
            )
        elif staffing.get("summary", {}).get("avgStaff") is not None:
            avg_staff = staffing["summary"]["avgStaff"]
            items.append(
                {
                    "label": "적정인력 참고",
                    "text": f"최근 평균 실근무인력 {avg_staff}명 수준의 배치를 검토할 수 있습니다.",
                }
            )

        risks: list[str] = []
        if (transport.get("summary", {}) or {}).get("overageOfficeCount", 0) > 0:
            risks.append("쿼터 초과 집중국")
        if (equipment.get("summary", {}) or {}).get("ipsRate", 100) < (equipment.get("summary", {}) or {}).get(
            "ipsTarget", 97
        ):
            risks.append("IPS 하락")
        if (safety.get("summary", {}) or {}).get("incidentCount", 0) > 0:
            risks.append("안전사고 후속 관리")
        if risks:
            items.append(
                {
                    "label": "주요 위험요인",
                    "text": ", ".join(risks) + "에 대한 사전 점검이 도움이 될 수 있습니다.",
                }
            )

        if not items:
            items.append(
                {
                    "label": "참고",
                    "text": "충분한 과거 데이터가 없어 내일 전망을 제시하기 어렵습니다.",
                }
            )
        return items
