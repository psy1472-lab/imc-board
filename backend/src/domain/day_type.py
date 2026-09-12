from __future__ import annotations

from datetime import date, timedelta

# 법정 공휴일 + 대체공휴일 (2025~2026, 운영 보고서 분석용)
KR_REGULAR_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2025, 1, 1),
        date(2025, 1, 28),
        date(2025, 1, 29),
        date(2025, 1, 30),
        date(2025, 3, 1),
        date(2025, 3, 3),
        date(2025, 5, 5),
        date(2025, 5, 6),
        date(2025, 6, 6),
        date(2025, 8, 15),
        date(2025, 10, 3),
        date(2025, 10, 6),
        date(2025, 10, 7),
        date(2025, 10, 8),
        date(2025, 10, 9),
        date(2025, 12, 25),
        date(2026, 1, 1),
        date(2026, 2, 16),
        date(2026, 2, 17),
        date(2026, 2, 18),
        date(2026, 3, 1),
        date(2026, 3, 2),
        date(2026, 5, 5),
        date(2026, 5, 24),
        date(2026, 5, 25),  # 부처님오신날 대체공휴일
        date(2026, 6, 6),
        date(2026, 7, 17),  # 제헌절 (2026 공휴일 부활)
        date(2026, 8, 15),
        date(2026, 8, 17),
        date(2026, 9, 24),
        date(2026, 9, 25),
        date(2026, 9, 26),
        date(2026, 10, 3),
        date(2026, 10, 5),
        date(2026, 10, 9),
        date(2026, 12, 25),
    }
)

# 국무회의·선거법 등에 따른 임시공휴일 (추가 지정 시 이 목록을 갱신)
KR_TEMPORARY_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2023, 10, 2),  # 추석-개천절 징검다리
        date(2024, 10, 1),  # 국군의 날 76주년
        date(2025, 1, 27),  # 설 연휴 내수 회복
        date(2025, 6, 3),  # 제21대 대통령 선거
        date(2026, 6, 3),  # 제9회 전국동시지방선거
    }
)

KR_HOLIDAYS: frozenset[date] = KR_REGULAR_HOLIDAYS | KR_TEMPORARY_HOLIDAYS


def resolve_day_type(report_date: date) -> str:
    weekday = report_date.weekday()
    if report_date in KR_HOLIDAYS:
        return "holiday"
    if weekday == 5:
        return "saturday"
    if weekday == 6:
        return "sunday"
    return "weekday"


def is_public_holiday(report_date: date) -> bool:
    return report_date in KR_HOLIDAYS


def is_post_holiday(report_date: date) -> bool:
    """법정·임시 공휴일 직후 첫 평일인지 판정한다. 일반 월요일(일요 다음날)은 제외한다."""
    if resolve_day_type(report_date) != "weekday":
        return False
    previous = report_date - timedelta(days=1)
    if previous in KR_HOLIDAYS:
        return True
    if previous.weekday() == 6:
        friday = report_date - timedelta(days=3)
        saturday = report_date - timedelta(days=2)
        return friday in KR_HOLIDAYS or saturday in KR_HOLIDAYS
    return False


def days_since_holiday(report_date: date, *, lookback: int = 14) -> int:
    for offset in range(0, lookback + 1):
        if report_date - timedelta(days=offset) in KR_HOLIDAYS:
            return offset
    return lookback + 1


def days_until_holiday(report_date: date, *, lookahead: int = 14) -> int:
    for offset in range(0, lookahead + 1):
        if report_date + timedelta(days=offset) in KR_HOLIDAYS:
            return offset
    return lookahead + 1
