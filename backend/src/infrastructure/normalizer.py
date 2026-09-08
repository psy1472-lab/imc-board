from __future__ import annotations

import re
from datetime import date


NONE_TOKENS = {"없음", "-", "—", "n/a", "null", ""}
ZERO_TOKENS = {"없음", "-", "—"}


def _is_zero_token(value: str) -> bool:
    return value.strip() in ZERO_TOKENS


def clean_text(text: str) -> str:
    return text.replace("\uf000", "").replace("\u200b", "").strip()


def normalize_heading(text: str) -> str:
    return re.sub(r"\s+", "", text)


def parse_volume(value: str | None) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    raw = value.strip()
    if _is_zero_token(raw):
        return 0, raw
    if raw in NONE_TOKENS:
        return None, raw

    cleaned = raw.replace(",", "").replace("개", "").replace("통", "").strip()
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    man_match = re.match(r"^([\d.]+)만$", cleaned)
    if man_match:
        return int(float(man_match.group(1)) * 10000), raw

    cheon_match = re.match(r"^([\d.]+)천$", cleaned)
    if cheon_match:
        return int(float(cheon_match.group(1)) * 1000), raw

    if re.match(r"^[\d.]+$", cleaned):
        if "." in cleaned and float(cleaned) < 1000:
            return int(float(cleaned) * 10000), raw
        return int(float(cleaned)), raw

    return None, raw


def parse_volume_with_peer_man_context(
    value: str | None,
    *,
    peers_use_man_unit: bool = False,
) -> tuple[int | None, str | None]:
    """표준형 소통실적에서 총량만 '29.1개'처럼 만 단위가 빠진 경우 29.1만개로 해석."""
    if value is None:
        return None, None
    raw = value.strip()
    if peers_use_man_unit and raw.endswith("개") and "만" not in raw:
        numeric = raw.replace("개", "").replace(",", "").strip()
        if re.match(r"^[\d.]+$", numeric):
            normalized, _ = parse_volume(f"{numeric}만")
            return normalized, raw
    return parse_volume(value)


def parse_rate(value: str | None) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    raw = value.strip().replace("%", "")
    if raw in NONE_TOKENS:
        return None, value
    raw = re.sub(r"\.{2,}", ".", raw)
    try:
        return float(raw), value
    except ValueError:
        return None, value


def parse_int(value: str | None) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    raw = value.strip()
    if _is_zero_token(raw):
        return 0, raw
    if raw in NONE_TOKENS:
        return None, raw
    cleaned = raw.replace(",", "")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    try:
        return int(float(cleaned)), raw
    except ValueError:
        return None, raw


def to_int_or_zero(value: str | None) -> int:
    parsed, _ = parse_int(value)
    return parsed if parsed is not None else 0


def parse_report_date_from_title(text: str) -> date | None:
    patterns = [
        r"['\u2018\u2019]?\s*(\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})",
        r"['\u2018\u2019]?\s*(\d{2})\.(\d{1,2})\.(\d{1,2})",
        r"(\d{2})\.(\d{2})\.(\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        yy, mm, dd = match.groups()
        return date(2000 + int(yy), int(mm), int(dd))
    return None
