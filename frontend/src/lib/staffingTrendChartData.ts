import type { StaffingTrendSeries } from "../types/staffingAnalysis";
import { resolveTrendDate, splitShortDateWithWeekday } from "./dateFormat";
import { TREND_X_AXIS_PADDING } from "./trendChartLayout";

export type StaffingTrendChartPoint = {
  axisLabel: string;
  dateText: string;
  weekdayText: string;
  productivity: number | null;
  volume: number | null;
  avgStaff: number | null;
  peakStaff: number | null;
};

export const STAFFING_TREND_SYNC_ID = "staffing-trend-sync";
export const STAFFING_TREND_Y_AXIS_WIDTH = 56;

export const STAFFING_TREND_MARGIN = {
  top: 32,
  right: 16,
  left: 20,
  bottom: 0,
} as const;

export const STAFFING_TREND_MARGIN_WITH_AXIS = {
  top: 32,
  right: 16,
  left: 20,
  bottom: 36,
} as const;

export function buildStaffingTrendChartData(
  data: StaffingTrendSeries,
  referenceDate?: string,
): StaffingTrendChartPoint[] {
  const isWeekdayMode = data.mode === "weekday";

  return data.dates.map((shortDate, index) => {
    if (isWeekdayMode) {
      const label = data.labels?.[index] ?? shortDate;
      const countText = data.sampleCounts?.[index] ? `(${data.sampleCounts[index]}일)` : "";
      return {
        axisLabel: `${label}${countText}`,
        dateText: label,
        weekdayText: countText,
        productivity: data.productivity[index] ?? null,
        volume: data.volume[index] ?? null,
        avgStaff: data.avgStaff[index] ?? null,
        peakStaff: data.peakStaff[index] ?? null,
      };
    }

    const fullDate = resolveTrendDate(data.reportDates?.[index], shortDate, referenceDate);
    const { dateText, weekdayText } = splitShortDateWithWeekday(fullDate);
    return {
      axisLabel: `${dateText}${weekdayText}`,
      dateText,
      weekdayText,
      productivity: data.productivity[index] ?? null,
      volume: data.volume[index] ?? null,
      avgStaff: data.avgStaff[index] ?? null,
      peakStaff: data.peakStaff[index] ?? null,
    };
  });
}

export function getStaffingTrendXAxisProps(
  pointCount: number,
  isWeekdayMode: boolean,
  hideAxis = false,
  tickFill?: string,
) {
  const denseAxis = !isWeekdayMode && pointCount > 10;
  if (hideAxis) {
    return {
      dataKey: "axisLabel" as const,
      hide: true,
      height: 0,
    };
  }
  return {
    dataKey: "axisLabel" as const,
    interval: denseAxis ? ("preserveStartEnd" as const) : 0,
    angle: isWeekdayMode ? 0 : denseAxis ? -35 : -20,
    textAnchor: isWeekdayMode ? ("middle" as const) : ("end" as const),
    height: isWeekdayMode ? 36 : 52,
    tickMargin: 8,
    padding: TREND_X_AXIS_PADDING,
    tick: { fontSize: 11, fill: tickFill },
  };
}
