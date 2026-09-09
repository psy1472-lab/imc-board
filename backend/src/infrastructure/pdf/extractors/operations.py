from __future__ import annotations

import re
from datetime import date, time

from domain.entities import QuotaExchange, SortingMachine, TransportOffice
from domain.transport_quota import quota_overage, quota_status
from infrastructure.normalizer import parse_int, parse_rate, to_int_or_zero
from infrastructure.pdf.reader import PdfDocument


class QuotaExchangeExtractor:
    QUOTA_SECTION_PATTERN = re.compile(
        r"교환\s*및\s*수지\s*쿼\s*터\s*준\s*수\s*현\s*황([\s\S]+?)"
        r"(?:기계구분|배분\s*및\s*교환|소포구분기|$)",
    )

    def extract(self, document: PdfDocument, report_date: date) -> QuotaExchange:
        text = "\n".join(page.text for page in document.pages[:3])
        quarter_standard, quarter_actual, quarter_difference = self._parse_quota_row(text, "쿼터")
        exchange_standard, exchange_actual, exchange_difference = self._parse_quota_row(text, "교환")
        remaining_match = re.search(r"교환\s*잔량:\s*([^(\s]+)", text)

        exchange_remaining = 0 if remaining_match and "없음" in remaining_match.group(1) else None
        if remaining_match and remaining_match.group(1).strip().isdigit():
            exchange_remaining = int(remaining_match.group(1).strip())

        return QuotaExchange(
            report_date=report_date,
            quarter_standard=quarter_standard,
            quarter_actual=quarter_actual,
            quarter_difference=quarter_difference,
            exchange_standard=exchange_standard,
            exchange_actual=exchange_actual,
            exchange_difference=exchange_difference,
            exchange_remaining=exchange_remaining,
        )

    def _parse_quota_row(self, text: str, label: str) -> tuple[int | None, int | None, int | None]:
        section_match = self.QUOTA_SECTION_PATTERN.search(text)
        section = section_match.group(1) if section_match else ""
        if not section:
            return None, None, None
        match = re.search(rf"(?:^|\n|[-\s]){label}\s+([-\d]+(?:\s+[-\d]+)*)", section)
        if not match:
            return None, None, None

        parts = match.group(1).split()
        if len(parts) >= 7:
            standard = to_int_or_zero(parts[0])
            difference = to_int_or_zero(parts[3])
            actual = to_int_or_zero(parts[6])
            return standard, actual, difference

        if len(parts) >= 6:
            standard = to_int_or_zero(parts[0])
            difference = to_int_or_zero(parts[5])
            return standard, standard + difference, difference

        if len(parts) >= 4 and parts[1] == "-":
            standard = to_int_or_zero(parts[0])
            numeric_parts = [to_int_or_zero(part) for part in parts[2:]]
            for actual in numeric_parts:
                for difference in numeric_parts:
                    if actual - standard == difference:
                        return standard, actual, difference

        if len(parts) >= 4:
            standard = to_int_or_zero(parts[0])
            mid = to_int_or_zero(parts[1])
            actual = to_int_or_zero(parts[2])
            difference = to_int_or_zero(parts[3])
            if actual - standard == difference or actual - standard - mid == difference:
                return standard, actual, difference

        return None, None, None


class TransportExtractor:
    END_PATTERN = re.compile(
        r"(?P<imc_vol>\d{1,3}(?:,\d{3})+|\d+)\s+"
        r"(?P<imc_veh>\d+)\s+"
        r"(?P<quota>-|\d+)\s+"
        r"(?P<quota_daily>-|\d+)\s+"
        r"(?P<difference>-?\d+)\s+"
        r"(?P<time>\d{2}:\d{2})"
        r"(?:\s+(?P<roll>[\d-]+)\s+(?P<flat>[\d-]+))?"
    )
    OFFICE_PATTERN = re.compile(r"([가-힣]+(?:집|물류|해상|인바운드)|[가-힣]+물)(?=\s)")

    def extract(self, document: PdfDocument, report_date: date) -> list[TransportOffice]:
        texts = self._transport_page_texts(document)
        if not texts:
            return []

        offices: list[TransportOffice] = []
        for text in texts:
            offices.extend(self._extract_offices_from_text(text, report_date))
        return self._dedupe_offices(offices)

    def _dedupe_offices(self, offices: list[TransportOffice]) -> list[TransportOffice]:
        unique: dict[str, TransportOffice] = {}
        for office in offices:
            unique.setdefault(office.office_name, office)
        return list(unique.values())

    def _transport_page_texts(self, document: PdfDocument) -> list[str]:
        matched: list[str] = []
        for page in document.pages:
            compact = page.text.replace(" ", "")
            if "집중국별쿼터발송" in compact or "집중국별쿼터" in compact:
                matched.append(page.text)
        if matched:
            return matched
        if len(document.pages) >= 3:
            return [document.pages[2].text]
        return []

    def _extract_offices_from_text(self, text: str, report_date: date) -> list[TransportOffice]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        offices: list[TransportOffice] = []

        for line in lines:
            if "합계" in line or "집중국" in line or line.startswith("※"):
                continue

            matches = list(self.END_PATTERN.finditer(line))
            if not matches:
                continue

            office_names = self.OFFICE_PATTERN.findall(line)
            if not office_names:
                continue

            match = matches[-1]
            vehicles_actual = int(match.group("imc_veh"))
            vehicles_quota = self._dash_int(match.group("quota_daily"))
            arrival_time = match.group("time")
            volume_text = match.group("imc_vol").replace(",", "")
            volume = int(volume_text) if volume_text.isdigit() else None
            overage = quota_overage(vehicles_actual, vehicles_quota) or 0
            status = quota_status(vehicles_actual, vehicles_quota)

            offices.append(
                TransportOffice(
                    report_date=report_date,
                    office_name=office_names[0],
                    volume=volume,
                    vehicles_actual=vehicles_actual,
                    vehicles_standard=vehicles_quota,
                    last_arrival_time=arrival_time,
                    delay_minutes=overage if overage > 0 else None,
                    status=status,
                )
            )
        return offices

    @staticmethod
    def _dash_int(raw: str) -> int:
        return 0 if raw == "-" else int(raw)


class SortingMachineExtractor:
    def extract(self, document: PdfDocument, report_date: date) -> SortingMachine | None:
        page_text = ""
        for page in document.pages:
            if "소포구분기" in page.text.replace(" ", ""):
                page_text = page.text
                break
        if not page_text:
            return None

        numbers = re.findall(r"[\d,]+(?:\.\d+)?", page_text)
        data_line_match = re.search(
            r"(\d{1,3}(?:,\d{3})+)\s+(\d{1,3}(?:,\d{3})+)\s+([\d.]+)\s+([\d.]+)",
            page_text,
        )
        if not data_line_match:
            return None

        total_supply, _ = parse_int(data_line_match.group(1))
        total_sorted, _ = parse_int(data_line_match.group(2))
        sorting_rate, _ = parse_rate(data_line_match.group(3))
        ips_rate, _ = parse_rate(data_line_match.group(4))

        tail_numbers = re.findall(r"([\d,]+)", page_text.split(data_line_match.group(0))[-1])
        avg_throughput = parse_int(tail_numbers[0])[0] if tail_numbers else None
        peak_throughput = parse_int(tail_numbers[1])[0] if len(tail_numbers) > 1 else None
        unread_count = parse_int(tail_numbers[5])[0] if len(tail_numbers) > 5 else None
        unread_rate = parse_rate(tail_numbers[-1])[0] if tail_numbers else None
        reject_rate = unread_rate

        return SortingMachine(
            report_date=report_date,
            total_supply=total_supply,
            total_sorted=total_sorted,
            sorting_rate=sorting_rate,
            ips_rate=ips_rate,
            reject_rate=reject_rate,
            shortcut_rate=parse_rate(tail_numbers[3])[0] if len(tail_numbers) > 3 else None,
            avg_throughput=avg_throughput,
            peak_throughput=peak_throughput,
            unread_count=unread_count,
            unread_rate=unread_rate,
        )


class SafetyCheckExtractor:
    CATEGORY_MAP = {
        "작업장": ("workplace", "작업장"),
        "건강관리": ("health", "건강관리"),
        "작업환경": ("environment", "작업환경"),
        "보호구": ("protective_equipment", "보호구"),
        "유해위험물": ("hazardous_material", "유해위험물"),
        "기계": ("machine", "기계·기구"),
        "전기": ("electricity", "전기"),
        "하역": ("loading", "하역·운반"),
        "소방": ("fire_safety", "소방"),
    }
    INCIDENT_SECTION_RE = re.compile(
        r"재해현황\s*(.+?)(?:※\s*불량|조치사항|\*\s*수시위험성평가|-\s*6\s*-)",
        re.DOTALL,
    )
    INCIDENT_PERSON_RE = re.compile(r"(?<![가-힣])([가-힣]{2,4})\(([남여])\)")

    def extract(self, document: PdfDocument, report_date: date):
        from domain.entities import SafetyCategory, SafetyIncident

        if not document.pages:
            return [], []

        page_text = self._find_safety_page_text(document)
        categories = self._extract_categories(page_text, report_date)
        incidents = self._extract_incidents(page_text, report_date)
        return categories, incidents

    def _find_safety_page_text(self, document: PdfDocument) -> str:
        for page in reversed(document.pages):
            text = page.text
            if "붙임6" in text or "관리감독자" in text or "재해현황" in text:
                return text
        return document.pages[-1].text

    def _extract_categories(self, page_text: str, report_date: date):
        from domain.entities import SafetyCategory

        categories: list[SafetyCategory] = []
        for keyword, (key, label) in self.CATEGORY_MAP.items():
            if keyword in page_text:
                categories.append(
                    SafetyCategory(
                        report_date=report_date,
                        category=key,
                        label=label,
                        passed_items=1,
                        total_items=1,
                        status="NORMAL",
                    )
                )
        return categories

    def _extract_incidents(self, page_text: str, report_date: date):
        from domain.entities import SafetyIncident

        section_match = self.INCIDENT_SECTION_RE.search(page_text)
        if not section_match:
            return []

        section = section_match.group(1)
        anchors = list(self.INCIDENT_PERSON_RE.finditer(section))
        incidents: list[SafetyIncident] = []

        for index, match in enumerate(anchors):
            name, gender = match.group(1), match.group(2)
            lookback_start = anchors[index - 1].end() if index > 0 else 0
            block_end = anchors[index + 1].start() if index + 1 < len(anchors) else len(section)
            line_start = max(0, match.start() - 40)
            line = section[line_start : match.end() + 40]

            prefix = section[lookback_start : match.start()]
            prefix_lines = [line.strip() for line in prefix.splitlines() if line.strip()]
            if prefix_lines and "부서명" in prefix_lines[0]:
                prefix_lines = prefix_lines[1:]
            narrative_prefix = prefix_lines[-1] if prefix_lines else ""
            body = section[match.start():block_end]
            if narrative_prefix and narrative_prefix not in body:
                body = f"{narrative_prefix} {body}".strip()

            department = self._extract_department(line, name, gender)
            time_match = re.search(r"\b(\d{2}:\d{2})\b", line) or re.search(
                r"\b(\d{2}:\d{2})\b", section[match.end() : match.end() + 40]
            )
            description = self._extract_incident_description(body, name, gender)

            incidents.append(
                SafetyIncident(
                    report_date=report_date,
                    department=department,
                    victim_name=name,
                    gender=gender,
                    occurrence_time=time_match.group(1) if time_match else None,
                    description=description,
                )
            )
        return incidents

    def _extract_department(self, block: str, name: str, gender: str) -> str | None:
        before_name = re.search(
            rf"(?:^|\s)((?:\d+팀)|(?:[가-힣]{{1,6}}(?:과|팀)))\s+{re.escape(name)}\({gender}\)",
            block,
        )
        if before_name:
            return before_name.group(1)

        after_name = re.search(
            rf"{re.escape(name)}\({gender}\).{{0,40}}?((?:\d+팀)|(?:[가-힣]{{1,6}}(?:과|팀)))",
            block,
            re.DOTALL,
        )
        if after_name:
            return after_name.group(1)
        return None

    def _extract_incident_description(self, block: str, name: str, gender: str) -> str:
        text = block
        text = re.sub(r"부서명.*?재해경위", " ", text)
        text = re.sub(rf"{re.escape(name)}\({gender}\)", " ", text)
        text = re.sub(r"(?<![가-힣])(?:\d+팀|[가-힣]{1,6}(?:과|팀))(?=\s)", " ", text)
        text = re.sub(r"우정실무원|\(공무직\)|\(한시직\)|한시직|공무직", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" -")
        return text or "재해경위 정보 없음"
