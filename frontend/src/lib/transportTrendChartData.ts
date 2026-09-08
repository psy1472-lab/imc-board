import type { TransportTrendSeries } from "../types/transportAnalysis";
import { resolveTrendDate, splitShortDateWithWeekday } from "./dateFormat";

export type TransportTrendChartPoint = {
  axisLabel: string;
  dateText: string;
  weekdayText: string;
  quarterComplianceRate: number | null;
  exchangeComplianceRate: number | null;
  overageOfficeCount: number | null;
};

export const TRANSPORT_TREND_MARGIN_WITH_AXIS = {
  top: 32,
  right: 16,
  left: 8,
  bottom: 36,
} as const;

export function buildTransportTrendChartData(
  data: TransportTrendSeries,
  referenceDate?: string,
): TransportTrendChartPoint[] {
  const isWeekdayMode = data.mode === "weekday";

  return data.dates.map((shortDate, index) => {
    if (isWeekdayMode) {
      const label = data.labels?.[index] ?? shortDate;
      const countText = data.sampleCounts?.[index] ? `(${data.sampleCounts[index]}일)` : "";
      return {
        axisLabel: `${label}${countText}`,
        dateText: label,
        weekdayText: countText,
        quarterComplianceRate: data.quarterComplianceRate[index] ?? null,
        exchangeComplianceRate: data.exchangeComplianceRate[index] ?? null,
        overageOfficeCount: data.overageOfficeCount[index] ?? null,
      };
    }

    const fullDate = resolveTrendDate(data.reportDates?.[index], shortDate, referenceDate);
    const { dateText, weekdayText } = splitShortDateWithWeekday(fullDate);
    return {
      axisLabel: `${dateText}${weekdayText}`,
      dateText,
      weekdayText,
      quarterComplianceRate: data.quarterComplianceRate[index] ?? null,
      exchangeComplianceRate: data.exchangeComplianceRate[index] ?? null,
      overageOfficeCount: data.overageOfficeCount[index] ?? null,
    };
  });
}

export function getTransportTrendXAxisProps(
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
