from __future__ import annotations

from dataclasses import dataclass

import pdfplumber

from infrastructure.normalizer import clean_text


@dataclass
class PdfPage:
    index: int
    text: str
    tables: list[list[list[str | None]]]


@dataclass
class PdfDocument:
    path: str
    pages: list[PdfPage]

    @property
    def full_text(self) -> str:
        return "\n".join(page.text for page in self.pages)


class PdfReader:
    def read(self, path: str) -> PdfDocument:
        pages: list[PdfPage] = []
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages):
                text = clean_text(page.extract_text() or "")
                tables = page.extract_tables() or []
                pages.append(PdfPage(index=index, text=text, tables=tables))
        return PdfDocument(path=path, pages=pages)
