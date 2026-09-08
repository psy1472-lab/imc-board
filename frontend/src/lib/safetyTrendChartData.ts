import type { SafetyTrendSeries } from "../types/safetyAnalysis";
import { resolveTrendDate, splitShortDateWithWeekday } from "./dateFormat";

export type SafetyTrendChartPoint = {
  axisLabel: string;
  dateText: string;
  weekdayText: string;
  incidentCount: number | null;
  warningCount: number | null;
  safetyPassRate: number | null;
};

export const SAFETY_TREND_MARGIN_WITH_AXIS = {
  top: 32,
  right: 16,
  left: 8,
  bottom: 36,
} as const;

export function buildSafetyTrendChartData(
  data: SafetyTrendSeries,
  referenceDate?: string,
): SafetyTrendChartPoint[] {
  const isWeekdayMode = data.mode === "weekday";

  return data.dates.map((shortDate, index) => {
    if (isWeekdayMode) {
      const label = data.labels?.[index] ?? shortDate;
      const countText = data.sampleCounts?.[index] ? `(${data.sampleCounts[index]}일)` : "";
      return {
        axisLabel: `${label}${countText}`,
        dateText: label,
        weekdayText: countText,
        incidentCount: data.incidentCount[index] ?? null,
        warningCount: data.warningCount[index] ?? null,
        safetyPassRate: data.safetyPassRate[index] ?? null,
      };
    }

    const fullDate = resolveTrendDate(data.reportDates?.[index], shortDate, referenceDate);
    const { dateText, weekdayText } = splitShortDateWithWeekday(fullDate);
    return {
      axisLabel: `${dateText}${weekdayText}`,
      dateText,
      weekdayText,
      incidentCount: data.incidentCount[index] ?? null,
      warningCount: data.warningCount[index] ?? null,
      safetyPassRate: data.safetyPassRate[index] ?? null,
    };
  });
}

export function getSafetyTrendXAxisProps(
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
