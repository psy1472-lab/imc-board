export const REPORT_FORMAT_LABELS: Record<string, string> = {
  standard: "평일형",
  compact: "축약형",
};

export const DAY_TYPE_LABELS: Record<string, string> = {
  weekday: "평일",
  saturday: "토요일",
  sunday: "일요일",
  holiday: "공휴일",
};

export function formatReportFormat(value?: string | null): string {
  if (!value) return "-";
  return REPORT_FORMAT_LABELS[value] ?? value;
}

export function formatDayType(value?: string | null): string {
  if (!value) return "-";
  return DAY_TYPE_LABELS[value] ?? value;
}

export function isCompactReport(format?: string | null): boolean {
  return format === "compact";
}
