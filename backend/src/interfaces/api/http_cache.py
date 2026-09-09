from __future__ import annotations

REPORT_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300"


def build_report_etag(report_date: str, token: str, ingested_at: str | None) -> str:
    return f'W/"{report_date}:{token}:{ingested_at or "0"}"'


def if_none_match_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    candidates = [part.strip() for part in if_none_match.split(",") if part.strip()]
    return etag in candidates or "*" in candidates
