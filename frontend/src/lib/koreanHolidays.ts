/** 법정 공휴일 + 대체공휴일 (backend/src/domain/day_type.py 와 동기화) */
const KR_REGULAR_HOLIDAY_ISO = new Set([
  "2025-01-01",
  "2025-01-28",
  "2025-01-29",
  "2025-01-30",
  "2025-03-01",
  "2025-03-03",
  "2025-05-05",
  "2025-05-06",
  "2025-06-06",
  "2025-08-15",
  "2025-10-03",
  "2025-10-06",
  "2025-10-07",
  "2025-10-08",
  "2025-10-09",
  "2025-12-25",
  "2026-01-01",
  "2026-02-16",
  "2026-02-17",
  "2026-02-18",
  "2026-03-01",
  "2026-03-02",
  "2026-05-05",
  "2026-05-24",
  "2026-05-25",
  "2026-06-06",
  "2026-07-17",
  "2026-08-15",
  "2026-08-17",
  "2026-09-24",
  "2026-09-25",
  "2026-09-26",
  "2026-10-03",
  "2026-10-05",
  "2026-10-09",
  "2026-12-25",
]);

/** 국무회의·선거법 등 임시공휴일 (추가 지정 시 이 목록을 갱신) */
const KR_TEMPORARY_HOLIDAY_ISO = new Set([
  "2023-10-02", // 추석-개천절 징검다리
  "2024-10-01", // 국군의 날 76주년
  "2025-01-27", // 설 연휴 내수 회복
  "2025-06-03", // 제21대 대통령 선거
  "2026-06-03", // 제9회 전국동시지방선거
]);

const KR_HOLIDAY_ISO = new Set([...KR_REGULAR_HOLIDAY_ISO, ...KR_TEMPORARY_HOLIDAY_ISO]);

export function isKoreanHoliday(isoDate: string): boolean {
  return KR_HOLIDAY_ISO.has(isoDate);
}

export function isKoreanTemporaryHoliday(isoDate: string): boolean {
  return KR_TEMPORARY_HOLIDAY_ISO.has(isoDate);
}

export type CalendarDayKind = "holiday" | "sunday" | "saturday" | "weekday";

export function resolveCalendarDayKind(isoDate: string, dayOfWeek: number): CalendarDayKind {
  if (isKoreanHoliday(isoDate)) return "holiday";
  if (dayOfWeek === 0) return "sunday";
  if (dayOfWeek === 6) return "saturday";
  return "weekday";
}
