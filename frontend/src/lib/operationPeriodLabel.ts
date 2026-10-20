import type { OperationPeriodType } from "../types/operationPeriod";

const NOTE_SHORT_NAMES: Array<{ pattern: RegExp; label: string }> = [
  { pattern: /추석/, label: "추석" },
  { pattern: /가을걷이|수확/, label: "가을걷이" },
  { pattern: /휴식/, label: "하계휴식" },
  { pattern: /(^|[^가-힣])설([^가-힣]|$)/, label: "설" },
  { pattern: /쇼핑/, label: "쇼핑" },
];

const TYPE_SHORT_NAMES: Record<OperationPeriodType, string> = {
  post_shopping_discount: "쇼핑",
  special_communication: "특별소통",
  no_parcel_day: "하계휴식",
  harvest_season: "가을걷이",
};

function periodYear(startDate: string) {
  const match = startDate.match(/^(\d{4})/);
  return match?.[1] ?? "";
}

function shortPeriodName(note: string | null | undefined, periodType?: string) {
  const source = note?.trim() ?? "";
  for (const rule of NOTE_SHORT_NAMES) {
    if (rule.pattern.test(source)) return rule.label;
  }
  if (periodType && periodType in TYPE_SHORT_NAMES) {
    return TYPE_SHORT_NAMES[periodType as OperationPeriodType];
  }
  return "";
}

export function formatNamedPeriodLabel(
  startDate: string,
  endDate: string,
  note?: string | null,
  periodType?: string,
) {
  const range = startDate === endDate ? startDate : `${startDate}~${endDate}`;
  const year = periodYear(startDate);
  const name = shortPeriodName(note, periodType);
  if (!year || !name) return range;
  return `${year}${name}(${range})`;
}
