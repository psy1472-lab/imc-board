from __future__ import annotations

import re
from datetime import date, time

from domain.entities import MachineSortingLine, QuotaExchange, SortingMachine, TransportOffice
from domain.transport_quota import quota_overage, quota_status
from infrastructure.normalizer import normalize_heading, parse_int, parse_rate, to_int_or_zero
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
            # 기준 … 초과 계 회차: 마지막이 회차(0 근처)이고 계-기준=초과
            maybe_actual = to_int_or_zero(parts[5])
            maybe_difference = to_int_or_zero(parts[4])
            maybe_round = to_int_or_zero(parts[6])
            if (
                maybe_actual > 0
                and abs(maybe_round) <= 2
                and maybe_actual - standard == maybe_difference
            ):
                return standard, maybe_actual, maybe_difference
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


class MachineSortingExtractor:
    DECK_RE = re.compile(r"([123])\s*단")
    DECK_LINE_RE = re.compile(r"([123])단\s+([\d,]+)\s+([\d.]+)")
    SECTION_RE = re.compile(
        r"기계구분\s*/\s*수작업[\s\S]+?(?:소포위탁배달원|중점추진|$)",
    )

    def extract(self, document: PdfDocument, report_date: date) -> list[MachineSortingLine]:
        for page in document.pages:
            heading = normalize_heading(page.text)
            for table in page.tables or []:
                lines = self._from_table(table, report_date)
                if self._is_usable(lines):
                    return lines
            if "기계구분" in heading and "수작업" in heading:
                lines = self._from_text(page.text, report_date)
                if self._is_usable(lines):
                    return lines
        return []

    def _is_usable(self, lines: list[MachineSortingLine]) -> bool:
        decks = {(item.stream, item.deck) for item in lines}
        return len(decks) >= 3

    def _norm(self, value: str | None) -> str:
        return re.sub(r"\s+", "", value or "")

    def _from_table(self, table, report_date: date) -> list[MachineSortingLine]:
        if not table:
            return []
        header_blob = "".join(self._norm(cell) for row in table[:3] for cell in row)
        if "기계구분" not in header_blob or "점유비" not in header_blob:
            return []

        volume_idx, share_idx = 2, 3
        for row in table[:3]:
            for index, cell in enumerate(row):
                normalized = self._norm(cell)
                if normalized == "기계구분":
                    volume_idx = index
                elif normalized == "점유비":
                    share_idx = index

        current_stream: str | None = None
        lines: list[MachineSortingLine] = []
        seen: set[tuple[str, int]] = set()
        for row in table:
            cells = list(row or [])
            joined = "".join(self._norm(cell) for cell in cells)
            if "합계" in joined:
                continue

            first = self._norm(cells[0]) if cells else ""
            if "발송" in first:
                current_stream = "dispatch"
            elif "도착" in first:
                current_stream = "arrival"

            deck = None
            for cell in cells[:3]:
                match = self.DECK_RE.search(self._norm(cell))
                if match:
                    deck = int(match.group(1))
                    break
            if deck is None or current_stream is None:
                continue

            key = (current_stream, deck)
            if key in seen:
                continue
            volume_raw = cells[volume_idx] if len(cells) > volume_idx else None
            share_raw = cells[share_idx] if len(cells) > share_idx else None
            volume, _ = parse_int(volume_raw)
            share_rate, _ = parse_rate(share_raw)
            if volume is None and share_rate is None:
                continue
            seen.add(key)
            lines.append(
                MachineSortingLine(
                    report_date=report_date,
                    stream=current_stream,
                    deck=deck,
                    volume=volume,
                    share_rate=share_rate,
                )
            )
        return lines

    def _from_text(self, text: str, report_date: date) -> list[MachineSortingLine]:
        section_match = self.SECTION_RE.search(text)
        section = section_match.group(0) if section_match else text
        matches = self.DECK_LINE_RE.findall(section)
        if len(matches) < 3:
            return []

        expected = [1, 2, 3, 1, 2, 3]
        streams = ["dispatch", "dispatch", "dispatch", "arrival", "arrival", "arrival"]
        lines: list[MachineSortingLine] = []
        for index, (deck_raw, volume_raw, share_raw) in enumerate(matches[:6]):
            if int(deck_raw) != expected[index]:
                return []
            volume, _ = parse_int(volume_raw)
            share_rate, _ = parse_rate(share_raw)
            lines.append(
                MachineSortingLine(
                    report_date=report_date,
                    stream=streams[index],
                    deck=int(deck_raw),
                    volume=volume,
                    share_rate=share_rate,
                )
            )
        return lines


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
        r"재해현황\s*(.+?)(?:\*\s*수시위험성평가|-\s*[56]\s*-|$)",
        re.DOTALL,
    )
    INCIDENT_PERSON_RE = re.compile(r"(?<![가-힣])([가-힣]{2,4})\(([남여])\)")
    DEPARTMENT_RE = re.compile(r"(?:물류\d+과|\d+팀|[가-힣]{1,6}(?:과|팀))(?!상)")
    INJURY_TYPE_RE = re.compile(r"(찰과상|타박상|염좌|열상|창상|골절|화상|자상|절단|좌상|출혈|끼임)")
    DISPATCH_NOISE_RE = re.compile(
        r"(?:[가-힣]\s*){1,4}집\s+[가-힣외,\d\s국]+[’']\d{2}\.\d{1,2}월[\d,.\s↑대]+"
    )
    FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９：", "0123456789:")
    ACTION_BOILERPLATE_RE = re.compile(r"\*\s*수시위험성평가.*")

    def extract(self, document: PdfDocument, report_date: date):
        from domain.entities import SafetyCategory

        if not document.pages:
            return [], []

        page = self._find_safety_page(document)
        page_text = page.text if page else document.pages[-1].text
        tables = page.tables if page else []
        categories = self._extract_categories(page_text, report_date)
        incidents = self._extract_incidents_from_tables(tables, report_date)
        if incidents is None:
            incidents = self._extract_incidents_from_text(page_text, report_date)
        return categories, incidents

    def _find_safety_page(self, document: PdfDocument):
        for page in reversed(document.pages):
            compact = page.text.replace(" ", "")
            if "붙임6" in compact or "관리감독자" in compact or "재해현황" in compact:
                return page
        return document.pages[-1]

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

    def _extract_incidents_from_tables(self, tables, report_date: date):
        found_header = False
        incidents = []
        for table in tables or []:
            parsed = self._parse_incident_table(table, report_date)
            if parsed is not None:
                found_header = True
                incidents.extend(parsed)
        if found_header:
            return incidents
        return None

    def _parse_incident_table(self, table, report_date: date):
        from domain.entities import SafetyIncident

        header_index = None
        columns = None
        for index, row in enumerate(table):
            cells = self._row_cells(row)
            if self._is_incident_header(cells):
                header_index = index
                columns = self._incident_column_map(cells)
                break
        if header_index is None or columns is None:
            return None

        incidents: list[SafetyIncident] = []
        last_department: str | None = None
        for row in table[header_index + 1 :]:
            cells = self._row_cells(row)
            row_text = " ".join(cells)
            person = self._first_person(row_text)
            if person is None:
                if incidents and "조치사항" in row_text.replace(" ", ""):
                    action = self._extract_action(row_text)
                    if action:
                        current = incidents[-1].description or ""
                        if action not in current:
                            incidents[-1].description = f"{current} / 조치사항: {action}".strip(" /")
                continue

            name, gender = person
            department = self._clean_department(self._cell_at(cells, columns.get("department"))) or last_department
            if department:
                last_department = department
            occurrence_time = self._extract_time(
                self._cell_at(cells, columns.get("time")) or row_text
            )
            injury_type = self._extract_injury_type(
                self._cell_at(cells, columns.get("injury")) or row_text
            )
            description = self._clean_description(
                self._cell_at(cells, columns.get("description")) or "",
                name,
                gender,
            )
            incidents.append(
                SafetyIncident(
                    report_date=report_date,
                    department=department,
                    victim_name=name,
                    gender=gender,
                    occurrence_time=occurrence_time,
                    injury_type=injury_type,
                    description=description,
                )
            )
        return incidents

    def _extract_incidents_from_text(self, page_text: str, report_date: date):
        from domain.entities import SafetyIncident

        section_match = self.INCIDENT_SECTION_RE.search(page_text)
        if not section_match:
            return []

        section = self.DISPATCH_NOISE_RE.sub(" ", section_match.group(1))
        anchors = list(self.INCIDENT_PERSON_RE.finditer(section))
        incidents: list[SafetyIncident] = []

        for index, match in enumerate(anchors):
            name, gender = match.group(1), match.group(2)
            lookback_start = anchors[index - 1].end() if index > 0 else 0
            block_end = anchors[index + 1].start() if index + 1 < len(anchors) else len(section)
            line_start = max(0, match.start() - 40)
            line = section[line_start : match.end() + 80]
            body = section[lookback_start:block_end]
            department = self._extract_department(line, name, gender)
            description = self._clean_description(body, name, gender)
            incidents.append(
                SafetyIncident(
                    report_date=report_date,
                    department=department,
                    victim_name=name,
                    gender=gender,
                    occurrence_time=self._extract_time(line) or self._extract_time(body),
                    injury_type=self._extract_injury_type(body),
                    description=description,
                )
            )
        return incidents

    def _is_incident_header(self, cells: list[str]) -> bool:
        text = "".join(cells)
        return "부서명" in text and "재해경위" in text and "성명" in text

    def _incident_column_map(self, cells: list[str]) -> dict[str, int]:
        compact = [re.sub(r"\s+", "", cell) for cell in cells]
        mapping: dict[str, int] = {}
        for index, cell in enumerate(compact):
            if "department" not in mapping and "부서명" in cell:
                mapping["department"] = index
            elif "name" not in mapping and "성명" in cell:
                mapping["name"] = index
            elif "time" not in mapping and "발생시간" in cell:
                mapping["time"] = index
            elif "injury" not in mapping and "상해종류" in cell:
                mapping["injury"] = index
            elif "description" not in mapping and "재해경위" in cell:
                mapping["description"] = index
        return mapping

    def _row_cells(self, row) -> list[str]:
        return [re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip() for cell in row]

    def _cell_at(self, cells: list[str], index: int | None) -> str:
        if index is None or index < 0 or index >= len(cells):
            return ""
        return cells[index]

    def _first_person(self, text: str) -> tuple[str, str] | None:
        match = self.INCIDENT_PERSON_RE.search(text)
        if not match:
            return None
        return match.group(1), match.group(2)

    def _extract_department(self, block: str, name: str, gender: str) -> str | None:
        before_name = re.search(
            rf"(?:^|\s)({self.DEPARTMENT_RE.pattern})\s+{re.escape(name)}\({gender}\)",
            block,
        )
        if before_name:
            return self._clean_department(before_name.group(1))
        after_name = re.search(
            rf"{re.escape(name)}\({gender}\).{{0,40}}?({self.DEPARTMENT_RE.pattern})",
            block,
            re.DOTALL,
        )
        if after_name:
            return self._clean_department(after_name.group(1))
        return None

    def _clean_department(self, value: str | None) -> str | None:
        text = (value or "").strip()
        if not text or self.INJURY_TYPE_RE.fullmatch(text):
            return None
        match = self.DEPARTMENT_RE.search(text)
        return match.group(0) if match else None

    def _extract_time(self, text: str) -> str | None:
        normalized = text.translate(self.FULLWIDTH_DIGITS)
        match = re.search(r"\b(\d{1,2}:\d{2})\b", normalized)
        if not match:
            return None
        hour, minute = match.group(1).split(":")
        return f"{int(hour):02d}:{minute}"

    def _extract_injury_type(self, text: str) -> str | None:
        match = self.INJURY_TYPE_RE.search(text)
        return match.group(1) if match else None

    def _extract_action(self, text: str) -> str | None:
        cleaned = self.ACTION_BOILERPLATE_RE.sub("", text)
        match = re.search(r"조치사항\s*[:：]?\s*(.+)", cleaned)
        if not match:
            return None
        action = re.sub(r"\s+", " ", match.group(1)).strip(" -")
        return action or None

    def _clean_description(self, block: str, name: str, gender: str) -> str:
        text = self.DISPATCH_NOISE_RE.sub(" ", block)
        text = self.ACTION_BOILERPLATE_RE.sub(" ", text)
        text = re.sub(r"부서명.*?재해경위", " ", text)
        text = re.sub(rf"{re.escape(name)}\({gender}\)", " ", text)
        text = re.sub(r"(?<![가-힣])(?:물류\d+과|\d+팀|[가-힣]{1,6}(?:과|팀))(?!상)(?=\s)", " ", text)
        text = re.sub(r"우정실무원|\(공무직\)|\(한시직\)|한시직|공무직", " ", text)
        text = re.sub(r"[’']\d{2}\.\d{1,2}월", " ", text)
        text = re.sub(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" -")
        return text or "재해경위 정보 없음"
