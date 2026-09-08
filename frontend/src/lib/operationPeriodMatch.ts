import type { OperationPeriod, OperationPeriodType } from "../types/operationPeriod";

const PERIOD_TYPE_ORDER: OperationPeriodType[] = [
  "post_shopping_discount",
  "special_communication",
  "no_parcel_day",
];

export function isDateInOperationPeriod(date: string, period: OperationPeriod): boolean {
  return date >= period.startDate && date <= period.endDate;
}

function sortOperationPeriods(periods: OperationPeriod[]): OperationPeriod[] {
  return [...periods].sort((left, right) => {
    const typeOrder =
      PERIOD_TYPE_ORDER.indexOf(left.periodType) - PERIOD_TYPE_ORDER.indexOf(right.periodType);
    if (typeOrder !== 0) return typeOrder;
    if (left.startDate !== right.startDate) {
      return left.startDate.localeCompare(right.startDate);
    }
    return left.id - right.id;
  });
}

export function getActiveOperationPeriods(date: string, periods: OperationPeriod[]): OperationPeriod[] {
  const directlyActive = periods.filter((period) => isDateInOperationPeriod(date, period));
  return sortOperationPeriods(directlyActive);
}

export const OPERATION_PERIOD_STATUS: Record<OperationPeriodType, string> = {
  post_shopping_discount: "CAUTION",
  special_communication: "WARNING",
  no_parcel_day: "CRITICAL",
};
