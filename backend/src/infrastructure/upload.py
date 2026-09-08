from __future__ import annotations

import re
from pathlib import Path

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_upload_filename(filename: str) -> str:
    name = Path(filename).name
    if not name.lower().endswith(".pdf"):
        raise ValueError("PDF file required")
    stem = name[:-4]
    safe_stem = _SAFE_NAME.sub("_", stem).strip("._") or "report"
    return f"{safe_stem[:120]}.pdf"
