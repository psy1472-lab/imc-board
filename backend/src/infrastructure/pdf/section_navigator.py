from __future__ import annotations

from infrastructure.normalizer import normalize_heading
from infrastructure.pdf.reader import PdfDocument


class SectionNavigator:
    def find_page_containing(self, document: PdfDocument, heading: str) -> int | None:
        target = normalize_heading(heading)
        for page in document.pages:
            normalized = normalize_heading(page.text)
            if target in normalized:
                return page.index
        return None

    def get_page_text(self, document: PdfDocument, page_index: int) -> str:
        return document.pages[page_index].text

    def get_page_tables(self, document: PdfDocument, page_index: int):
        return document.pages[page_index].tables
