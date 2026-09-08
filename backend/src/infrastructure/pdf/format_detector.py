from __future__ import annotations

import re

from domain.format_profile import COMPACT_PROFILE, STANDARD_PROFILE, FormatProfile
from infrastructure.pdf.reader import PdfDocument
from infrastructure.pdf.section_navigator import SectionNavigator

_COMPACT_KPI_PATTERN = re.compile(r"소통물량\s*:\s*총\s*[\d,]+\s*개")
_STANDARD_KPI_PATTERN = re.compile(r"소통실적\s*:")
_STANDARD_SECTION_HEADINGS = (
    "시간대별 처리 및 인력투입 현황",
    "교환 및 수지 쿼터 준수현황",
    "관리감독자 안전보건 점검 일지",
)


class ReportFormatDetector:
    def __init__(self) -> None:
        self._navigator = SectionNavigator()

    def detect(self, document: PdfDocument) -> str:
        return self.detect_profile(document).name

    def detect_profile(self, document: PdfDocument) -> FormatProfile:
        text = document.pages[0].text if document.pages else ""

        if _COMPACT_KPI_PATTERN.search(text):
            return COMPACT_PROFILE
        if _STANDARD_KPI_PATTERN.search(text):
            return STANDARD_PROFILE

        for heading in _STANDARD_SECTION_HEADINGS:
            if self._navigator.find_page_containing(document, heading) is not None:
                return STANDARD_PROFILE

        if len(document.pages) <= 1:
            return COMPACT_PROFILE
        return STANDARD_PROFILE
