import type { OperationPeriod, OperationPeriodType } from "../types/operationPeriod";

const PERIOD_TYPE_ORDER: OperationPeriodType[] = [
  "post_shopping_discount",
  "special_communication",
  "no_parcel_day",
];

export function isDateInOperationPeriod(date: string, period: OperationPeriod): boolean {
  return date >= period.startDate && date <= period.endDate;
}

export function periodsOverlap(a: OperationPeriod, b: OperationPeriod): boolean {
  return a.startDate <= b.endDate && b.startDate <= a.endDate;
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
  const activeIds = new Set(directlyActive.map((period) => period.id));
  const activePostShopping = directlyActive.filter(
    (period) => period.periodType === "post_shopping_discount",
  );

  if (activePostShopping.length === 0) {
    return sortOperationPeriods(directlyActive);
  }

  const linkedSpecialCommunication = periods.filter((period) => {
    if (period.periodType !== "special_communication" || activeIds.has(period.id)) {
      return false;
    }
    return activePostShopping.some((shoppingPeriod) => periodsOverlap(shoppingPeriod, period));
  });

  return sortOperationPeriods([...directlyActive, ...linkedSpecialCommunication]);
}

export const OPERATION_PERIOD_STATUS: Record<OperationPeriodType, string> = {
  post_shopping_discount: "CAUTION",
  special_communication: "WARNING",
  no_parcel_day: "CRITICAL",
};
