const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"] as const;

function parseLocalDate(dateStr: string): Date | null {
  const isoMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    return new Date(Number(year), Number(month) - 1, Number(day));
  }
  return null;
}

export function formatShortDateWithWeekday(dateStr: string): string {
  const date = parseLocalDate(dateStr);
  if (!date) return dateStr;
  const weekday = WEEKDAYS[date.getDay()];
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}-${day}(${weekday})`;
}

export function splitShortDateWithWeekday(dateStr: string): { dateText: string; weekdayText: string } {
  const date = parseLocalDate(dateStr);
  if (!date) {
    return { dateText: dateStr, weekdayText: "" };
  }
  const weekday = WEEKDAYS[date.getDay()];
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return {
    dateText: `${month}-${day}`,
    weekdayText: `(${weekday})`,
  };
}

export function resolveTrendDate(
  reportDate: string | undefined,
  shortDate: string,
  referenceDate?: string,
): string {
  if (reportDate && /^\d{4}-\d{2}-\d{2}$/.test(reportDate)) {
    return reportDate;
  }
  if (/^\d{2}-\d{2}$/.test(shortDate) && referenceDate) {
    return `${referenceDate.slice(0, 4)}-${shortDate}`;
  }
  return reportDate ?? shortDate;
}

export function formatDateWithWeekday(dateStr: string): string {
  if (!dateStr) return "";
  const date = parseLocalDate(dateStr);
  if (!date) return dateStr;
  const weekday = WEEKDAYS[date.getDay()];
  return `${dateStr}(${weekday})`;
}

/** 배지 등 소형 UI용: 8.14~8.18 */
export function formatCompactPeriodRange(startDate: string, endDate: string): string {
  const formatPart = (dateStr: string) => {
    const date = parseLocalDate(dateStr);
    if (!date) return dateStr;
    const month = date.getMonth() + 1;
    const day = String(date.getDate()).padStart(2, "0");
    return `${month}.${day}`;
  };

  const start = formatPart(startDate);
  const end = formatPart(endDate);
  if (startDate === endDate) {
    return start;
  }
  return `${start}~${end}`;
}