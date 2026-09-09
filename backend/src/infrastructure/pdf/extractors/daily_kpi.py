from __future__ import annotations

import re
from datetime import date

from domain.entities import DailySummary
from domain.format_profile import FormatProfile, STANDARD_PROFILE
from domain.hour_slots import HOUR_SLOTS
from infrastructure.normalizer import clean_text, parse_report_date_from_title, parse_int, parse_volume, parse_volume_with_peer_man_context
from infrastructure.pdf.reader import PdfDocument


class DailyKpiExtractor:
    HOUR_SLOTS = HOUR_SLOTS

    def extract(self, document: PdfDocument) -> tuple[date, str | None, DailySummary]:
        text = clean_text(document.pages[0].text)
        report_date = parse_report_date_from_title(text)
        if report_date is None:
            raise ValueError("report_date not found in PDF title")

        center_match = re.search(r"(중부권광역우편물류센터|중부권IMC)", text)
        center_name = center_match.group(1) if center_match else None

        kpi_values = self._extract_kpi_values(text)
        if not kpi_values:
            raise ValueError("daily KPI block not found")

        (
            total_volume,
            dispatch_volume,
            arrival_volume,
            remaining_volume,
            raw_values,
        ) = kpi_values

        national_volume, national_raw = self._extract_national_volume(text)

        productivity_match = re.search(r"평균\s*인시당\s*처리\s*물량:\s*([\d.]+)개", text)
        productivity = (
            float(re.sub(r"\.{2,}", ".", productivity_match.group(1)))
            if productivity_match
            else None
        )

        communication_status = "NORMAL" if (remaining_volume or 0) == 0 else "WARNING"

        summary = DailySummary(
            report_date=report_date,
            center_name=center_name,
            national_volume=national_volume,
            total_volume=total_volume,
            dispatch_volume=dispatch_volume,
            arrival_volume=arrival_volume,
            remaining_volume=remaining_volume,
            productivity=productivity,
            communication_status=communication_status,
            raw_values={
                **raw_values,
                "national_volume": national_raw,
            },
        )
        return report_date, center_name, summary

    def _extract_kpi_values(self, text: str) -> tuple[int | None, int | None, int | None, int | None, dict] | None:
        volume_token = r"[\d.]+만개|[\d.]+개"
        remaining_label = r"(?:잔량|배분잔량)"

        standard_patterns = [
            # 기존: 소통실적 : 60.8만개(발송:43.3만개, 도착:17.5만개, 잔량: 없음)
            rf"소통실적\s*:\s*({volume_token})\s*\(발송:?\s*({volume_token}),\s*도착:?\s*({volume_token}),\s*{remaining_label}:?\s*([^)]+)\)",
            # 변형: 소통실적 : 49.4만개 (발송 36.6만개, 도착 12.8만개, 잔량 0.0만개)
            rf"소통실적\s*:\s*({volume_token})\s*\(발송\s+({volume_token}),\s*도착\s+({volume_token}),\s*{remaining_label}\s+([^)]+)\)",
            # 변형: 잔량 필드 없음 — 소통실적 : 32.6만개(발송: 24.1만개, 도착: 8.5만개)
            rf"소통실적\s*:\s*({volume_token})\s*\(발송:?\s*({volume_token}),\s*도착:?\s*({volume_token})\)",
        ]
        for pattern in standard_patterns:
            standard_match = re.search(pattern, text)
            if standard_match:
                return self._parse_standard_kpi_match(standard_match, text)

        compact_patterns = [
            # 기존: 소통물량 : 총 31,581개 (발송 29,721 배분 4,512)
            r"소통물량\s*:\s*총\s*([\d,]+)\s*개\s*\(발송\s*([\d,]+)\s*,?\s*(?:도착|배분)\s*([\d,]+)\s*\)",
            # 변형: 소통물량 :총 40,068개(발송 34,671 /도착 5,397) (단위:만개)
            r"소통물량\s*:\s*총\s*([\d,]+)\s*개\s*\(발송\s*([\d,]+)\s*[,/]?\s*(?:도착|배분)\s*([\d,]+)\s*\)",
        ]
        for pattern in compact_patterns:
            compact_match = re.search(pattern, text)
            if compact_match:
                return self._parse_compact_kpi_match(text, compact_match)

        return None

    def _parse_standard_kpi_match(
        self,
        match: re.Match[str],
        text: str,
    ) -> tuple[int | None, int | None, int | None, int | None, dict]:
        total_volume, total_raw = parse_volume_with_peer_man_context(
            match.group(1),
            peers_use_man_unit=any("만" in (match.group(i) or "") for i in (2, 3)),
        )
        dispatch_volume, dispatch_raw = parse_volume(match.group(2))
        arrival_volume, arrival_raw = parse_volume(match.group(3))
        if match.lastindex and match.lastindex >= 4 and match.group(4):
            remaining_volume, remaining_raw = parse_volume(match.group(4).strip().rstrip("*").strip())
        else:
            remaining_volume, remaining_raw = self._infer_remaining_volume(text)
        return (
            total_volume,
            dispatch_volume,
            arrival_volume,
            remaining_volume,
            {
                "total_volume": total_raw,
                "dispatch_volume": dispatch_raw,
                "arrival_volume": arrival_raw,
                "remaining_volume": remaining_raw,
            },
        )

    def _infer_remaining_volume(self, text: str) -> tuple[int | None, str | None]:
        summary = re.search(r"계\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+전국접수물량", text)
        if summary:
            return parse_volume(f"{summary.group(1)}만")
        return 0, "없음"

    def _parse_compact_kpi_match(
        self,
        text: str,
        match: re.Match[str],
    ) -> tuple[int | None, int | None, int | None, int | None, dict]:
        total_volume, total_raw = parse_volume(f"{match.group(1)}개")
        dispatch_volume, dispatch_raw = parse_volume(f"{match.group(2)}개")
        arrival_volume, arrival_raw = parse_volume(f"{match.group(3)}개")
        remaining_match = re.search(r"소\s*통\s*잔\s*량\s*:\s*([^\n]+)", text)
        if not remaining_match:
            remaining_match = re.search(r"소통잔량\s*:\s*([^\n]+)", text)
        remaining_raw = remaining_match.group(1).strip() if remaining_match else "없음"
        remaining_volume, remaining_parsed = parse_volume(remaining_raw)
        return (
            total_volume,
            dispatch_volume,
            arrival_volume,
            remaining_volume,
            {
                "total_volume": total_raw,
                "dispatch_volume": dispatch_raw,
                "arrival_volume": arrival_raw,
                "remaining_volume": remaining_parsed or remaining_raw,
            },
        )

    def _extract_national_volume(self, text: str) -> tuple[int | None, str | None]:
        matches = re.findall(r"전국접수물량\s*[:：]?\s*([\d.]+만)", text)
        for raw in matches:
            normalized = re.sub(r"\.{2,}", ".", raw.replace("만", "").strip())
            try:
                return int(float(normalized) * 10000), raw
            except ValueError:
                continue
        return None, None

    def extract_hourly(
        self,
        document: PdfDocument,
        report_date: date,
        profile: FormatProfile = STANDARD_PROFILE,
    ):
        from domain.entities import HourlyThroughput, StaffingHour

        text = document.pages[0].text
        section = self._extract_hourly_section(text)
        table_section = self._hourly_table_text(document)
        compact = profile.is_compact

        dispatch_match = self._match_volume_hour_row(section, table_section, "dispatch")
        arrival_match = self._match_volume_hour_row(section, table_section, "arrival")
        total_match = self._match_volume_hour_row(section, table_section, "total")

        dispatch_raw = self._strip_compact_row_subtotal(
            self._clean_hour_values(
                self._parse_hour_row(dispatch_match.group(1) if dispatch_match else "")
            ),
            dispatch_match.group(2) if dispatch_match else None,
        )
        arrival_raw = self._strip_compact_row_subtotal(
            self._clean_hour_values(
                self._parse_hour_row(arrival_match.group(1) if arrival_match else "")
            ),
            arrival_match.group(2) if arrival_match else None,
        )
        total_raw = self._clean_hour_values(
            self._parse_hour_row(total_match.group(1) if total_match else "")
        )

        total_values = self._align_hour_values(
            total_raw,
            total_match.group(2) if total_match else None,
            sparse=False,
        )

        if compact:
            dispatch_values, arrival_values = self._align_compact_sparse_rows(
                dispatch_raw,
                arrival_raw,
                total_values,
            )
        else:
            dispatch_values = self._align_hour_values(
                dispatch_raw,
                dispatch_match.group(2) if dispatch_match else None,
                sparse=False,
            )
            arrival_values = self._align_hour_values(
                arrival_raw,
                arrival_match.group(2) if arrival_match else None,
                sparse=False,
            )

        staff_match = re.search(
            r"⑪소포계[^\d]*((?:[\d.\-]+\s+)+[\d.\-]+)",
            text,
        )
        prod_match = re.search(
            r"인시당 처리물량\(처리물량/⑪\)\(개\)\s+((?:[\d.\-]+\s+)+[\d.\-]+)",
            text,
        )
        staff_values = self._align_hour_values(
            self._parse_hour_row(staff_match.group(1) if staff_match else ""),
            sparse=False,
        )
        prod_values = self._align_hour_values(
            self._parse_hour_row(prod_match.group(1) if prod_match else ""),
            sparse=False,
        )

        hourly: list[HourlyThroughput] = []
        staffing: list[StaffingHour] = []

        for idx, slot in enumerate(self.HOUR_SLOTS):
            dispatch = self._slot_volume(dispatch_values, idx)
            arrival = self._slot_volume(arrival_values, idx)
            total = self._slot_volume(total_values, idx)

            if compact:
                if total is not None:
                    if dispatch is not None:
                        arrival = max(total - dispatch, 0) or None
                    else:
                        arrival = total
                elif dispatch is not None or arrival is not None:
                    total = (dispatch or 0) + (arrival or 0)
            elif total is None and (dispatch is not None or arrival is not None):
                total = (dispatch or 0) + (arrival or 0)

            hourly.append(
                HourlyThroughput(
                    report_date=report_date,
                    hour_slot=slot,
                    dispatch_volume=dispatch,
                    arrival_volume=arrival,
                    total_volume=total,
                )
            )

            actual_staff = self._to_int(staff_values[idx] if idx < len(staff_values) else None)
            productivity = self._to_float(prod_values[idx] if idx < len(prod_values) else None)
            staffing.append(
                StaffingHour(
                    report_date=report_date,
                    hour_slot=slot,
                    actual_staff=actual_staff,
                    productivity=productivity,
                )
            )

        return hourly, staffing

    def _extract_hourly_section(self, text: str) -> str:
        for marker in ("시간대별 처리 및 인력투입 현황", "시간대별 처리"):
            idx = text.find(marker)
            if idx >= 0:
                return text[idx:]
        header_match = re.search(r"구\s*분\s+~18", text)
        if header_match:
            return text[header_match.start() :]
        return text

    def _is_compact_hourly_format(self, text: str) -> bool:
        return bool(re.search(r"소통물량\s*:\s*총\s*[\d,]+\s*개", text))

    def _strip_compact_row_subtotal(
        self,
        values: list[str | None],
        row_total: str | None,
    ) -> list[str | None]:
        if not values:
            return values
        cleaned = list(values)
        if row_total and cleaned[-1] is not None and self._values_match(cleaned[-1], row_total):
            return cleaned[:-1]
        if len(cleaned) >= 2 and cleaned[-1] is not None:
            parts = [self._to_volume(value) or 0 for value in cleaned[:-1] if value is not None]
            last = cleaned[-1]
            last_volume = self._to_volume(last)
            if parts and last_volume is not None and last_volume == sum(parts):
                return cleaned[:-1]
            if parts and "." in " ".join(value for value in cleaned[:-1] if value):
                try:
                    last_man_total = int(float(last) * 10000)
                    if sum(parts) == last_man_total:
                        return cleaned[:-1]
                except ValueError:
                    pass
        return cleaned

    def _align_compact_sparse_rows(
        self,
        dispatch_values: list[str | None],
        arrival_values: list[str | None],
        total_values: list[str | None],
    ) -> tuple[list[str | None], list[str | None]]:
        dispatch = [value for value in dispatch_values if value is not None]
        arrival = [value for value in arrival_values if value is not None]
        if not dispatch and not arrival:
            return self._align_sparse_hour_values(dispatch_values), self._align_sparse_hour_values(arrival_values)

        anchor = self._compact_anchor_index(total_values)
        dispatch_aligned = [None] * len(self.HOUR_SLOTS)
        arrival_aligned = [None] * len(self.HOUR_SLOTS)

        for index, value in enumerate(dispatch):
            slot_index = anchor + index
            if slot_index < len(self.HOUR_SLOTS):
                dispatch_aligned[slot_index] = value

        arrival_start = anchor + len(dispatch)
        for index, value in enumerate(arrival):
            slot_index = arrival_start + index
            if slot_index < len(self.HOUR_SLOTS):
                arrival_aligned[slot_index] = value

        return dispatch_aligned, arrival_aligned

    def _compact_anchor_index(self, total_values: list[str | None]) -> int:
        for index, value in enumerate(total_values):
            if self._to_volume(value):
                return index
        return 1

    def _hourly_table_text(self, document: PdfDocument) -> str:
        lines: list[str] = []
        for page in document.pages[:2]:
            for table in page.tables:
                for row in table:
                    line = " ".join(str(cell).replace("\n", " ") for cell in row if cell)
                    if line.strip():
                        lines.append(line)
        return "\n".join(lines)

    def _looks_like_man_volume_row(self, values: str) -> bool:
        return bool(re.search(r"\d+\.\d+", values))

    def _match_hour_row(self, section: str, row_type: str) -> re.Match[str] | None:
        patterns = {
            "dispatch": [
                r"처리\s*발송\s+((?:[\d.\-]+\s+)+[\d.\-]+)(?:\s+([\d.]+))?",
                # pdfplumber가 '처'를 잘라도 '발송 - 2.2 ...' 형태는 남는다.
                r"발\s*송\s+((?:[\d.\-]+\s+)+[\d.\-]+)(?:\s+([\d.]+))?",
            ],
            "arrival": [
                r"처리\s*(?:도착|배\s*분)\s+((?:[\d.\-]+\s+)+[\d.\-]+)(?:\s+([\d.]+))?",
                r"(?:도착|배\s*분)\s+((?:[\d.\-]+\s+)+[\d.\-]+)(?:\s+([\d.]+))?",
            ],
            "total": [
                r"소\s*계\s+((?:[\d.\-]+\s+)+[\d.\-]+)(?:\s+([\d.]+))?",
                r"(?:\(단위:만개\)\s*계|(?<!소\s)계)\s+((?:[\d.\-]+\s+)+[\d.\-]+)(?:\s+([\d.]+))?",
            ],
        }
        for pattern in patterns[row_type]:
            for match in re.finditer(pattern, section):
                if row_type == "total" or self._looks_like_man_volume_row(match.group(1)):
                    return match
        return None

    def _match_volume_hour_row(
        self,
        section: str,
        table_section: str,
        row_type: str,
    ) -> re.Match[str] | None:
        return self._match_hour_row(section, row_type) or self._match_hour_row(table_section, row_type)

    def _clean_hour_values(self, values: list[str | None]) -> list[str | None]:
        cleaned = list(values)
        while cleaned and cleaned[-1] is not None:
            last = cleaned[-1]
            if re.fullmatch(r"\d{1,2}", last):
                cleaned = cleaned[:-1]
                continue
            break

        max_columns = len(self.HOUR_SLOTS) + 2
        if len(cleaned) > max_columns:
            cleaned = cleaned[:max_columns]
        return cleaned

    def _align_hour_values(
        self,
        values: list[str | None],
        row_total: str | None = None,
        *,
        sparse: bool = False,
    ) -> list[str | None]:
        if not values:
            return [None] * len(self.HOUR_SLOTS)

        cleaned = list(values)
        if self._should_strip_trailing_subtotal(cleaned, row_total):
            cleaned = cleaned[:-1]

        if sparse and len(cleaned) < len(self.HOUR_SLOTS):
            return self._align_sparse_hour_values(cleaned)

        if len(cleaned) == len(self.HOUR_SLOTS):
            return cleaned

        if len(cleaned) == len(self.HOUR_SLOTS) - 1:
            return [None] + cleaned

        if len(cleaned) > len(self.HOUR_SLOTS):
            cleaned = cleaned[: len(self.HOUR_SLOTS)]

        if len(cleaned) < len(self.HOUR_SLOTS):
            cleaned = cleaned + [None] * (len(self.HOUR_SLOTS) - len(cleaned))

        return cleaned

    def _slot_volume(
        self,
        aligned: list[str | None],
        index: int,
    ) -> int | None:
        base = aligned[index] if index < len(aligned) else None
        return self._to_volume(base)

    def _align_sparse_hour_values(self, values: list[str | None]) -> list[str | None]:
        result = [None] * len(self.HOUR_SLOTS)
        if not values:
            return result

        non_dash = [value for value in values if value is not None]
        if not non_dash:
            return result

        # 소량 형식은 값이 19시~ 등 앞쪽 시간대부터 채워지는 경우가 많다.
        align_start = 1 if len(non_dash) <= 6 else max(0, len(self.HOUR_SLOTS) - len(non_dash))
        for index, value in enumerate(non_dash):
            slot_index = align_start + index
            if slot_index < len(self.HOUR_SLOTS):
                result[slot_index] = value
        return result

    def _should_strip_trailing_subtotal(
        self, values: list[str | None], row_total: str | None
    ) -> bool:
        if not values or values[-1] is None:
            return False
        last = values[-1]
        if row_total and self._values_match(last, row_total):
            return True
        return self._looks_like_row_subtotal(values)

    def _looks_like_row_subtotal(self, values: list[str | None]) -> bool:
        if not values or values[-1] is None:
            return False
        last_volume = self._to_volume(values[-1])
        if last_volume is None:
            return False
        hour_volumes = [self._to_volume(value) or 0 for value in values[:-1] if value is not None]
        if not hour_volumes:
            return False
        peak = max(hour_volumes)
        return last_volume > peak * 1.5 and last_volume >= sum(hour_volumes) * 0.5

    def _values_match(self, left: str, right: str) -> bool:
        left_volume = self._to_volume(left)
        right_volume = self._to_volume(right)
        if left_volume is None or right_volume is None:
            return left.strip() == right.strip()
        return left_volume == right_volume

    def _parse_hour_row(self, row: str, as_int: bool = True) -> list[str | None]:
        parts = row.split()
        values: list[str | None] = []
        for part in parts:
            if part == "-":
                values.append(None)
            else:
                values.append(part)
        return values

    def _to_volume(self, value: str | None) -> int | None:
        if value is None:
            return None
        normalized, _ = parse_volume(f"{value}만" if "." in value else value)
        return normalized

    def _to_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        parsed, _ = parse_int(value)
        return parsed

    def _to_float(self, value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(re.sub(r"\.{2,}", ".", value))
        except ValueError:
            return None
