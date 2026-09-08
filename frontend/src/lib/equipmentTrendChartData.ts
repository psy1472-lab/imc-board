import type { EquipmentTrendSeries } from "../types/equipmentAnalysis";
import { resolveTrendDate, splitShortDateWithWeekday } from "./dateFormat";

export type EquipmentTrendChartPoint = {
  axisLabel: string;
  dateText: string;
  weekdayText: string;
  sortingRate: number | null;
  ipsRate: number | null;
  rejectRate: number | null;
  unreadRate: number | null;
  avgThroughput: number | null;
  peakThroughput: number | null;
};

export const EQUIPMENT_TREND_MARGIN_WITH_AXIS = {
  top: 32,
  right: 16,
  left: 8,
  bottom: 36,
} as const;

export function buildEquipmentTrendChartData(
  data: EquipmentTrendSeries,
  referenceDate?: string,
): EquipmentTrendChartPoint[] {
  const isWeekdayMode = data.mode === "weekday";

  return data.dates.map((shortDate, index) => {
    if (isWeekdayMode) {
      const label = data.labels?.[index] ?? shortDate;
      const countText = data.sampleCounts?.[index] ? `(${data.sampleCounts[index]}일)` : "";
      return {
        axisLabel: `${label}${countText}`,
        dateText: label,
        weekdayText: countText,
        sortingRate: data.sortingRate[index] ?? null,
        ipsRate: data.ipsRate[index] ?? null,
        rejectRate: data.rejectRate[index] ?? null,
        unreadRate: data.unreadRate[index] ?? null,
        avgThroughput: data.avgThroughput[index] ?? null,
        peakThroughput: data.peakThroughput[index] ?? null,
      };
    }

    const fullDate = resolveTrendDate(data.reportDates?.[index], shortDate, referenceDate);
    const { dateText, weekdayText } = splitShortDateWithWeekday(fullDate);
    return {
      axisLabel: `${dateText}${weekdayText}`,
      dateText,
      weekdayText,
      sortingRate: data.sortingRate[index] ?? null,
      ipsRate: data.ipsRate[index] ?? null,
      rejectRate: data.rejectRate[index] ?? null,
      unreadRate: data.unreadRate[index] ?? null,
      avgThroughput: data.avgThroughput[index] ?? null,
      peakThroughput: data.peakThroughput[index] ?? null,
    };
  });
}

export function getEquipmentTrendXAxisProps(
  pointCount: number,
  isWeekdayMode: boolean,
  tickFill?: string,
) {
  const denseAxis = !isWeekdayMode && pointCount > 10;
  return {
    dataKey: "axisLabel" as const,
    interval: denseAxis ? ("preserveStartEnd" as const) : 0,
    angle: isWeekdayMode ? 0 : denseAxis ? -35 : -20,
    textAnchor: isWeekdayMode ? ("middle" as const) : ("end" as const),
    height: isWeekdayMode ? 36 : 52,
    tick: { fontSize: 11, fill: tickFill },
  };
}
