import type { VolumeTrendSeries } from "../types/volumeAnalysis";
import { resolveTrendDate, splitShortDateWithWeekday } from "./dateFormat";
import { TREND_X_AXIS_PADDING } from "./trendChartLayout";

export type TrendChartPoint = {
  axisLabel: string;
  dateText: string;
  weekdayText: string;
  totalVolume: number | null;
  dispatchVolume: number | null;
  arrivalVolume: number | null;
  nationalVolume: number | null;
  totalProcessingRate: number | null;
  dispatchProcessingRate: number | null;
  arrivalProcessingRate: number | null;
};

export const TREND_CHART_MARGIN = {
  top: 32,
  right: 16,
  left: 8,
  bottom: 0,
} as const;

export const TREND_CHART_MARGIN_WITH_AXIS = {
  top: 32,
  right: 16,
  left: 8,
  bottom: 36,
} as const;

export const TREND_CHART_MARGIN_COMPACT = {
  top: 8,
  right: 16,
  left: 8,
  bottom: 0,
} as const;

export const TREND_CHART_MARGIN_COMPACT_WITH_AXIS = {
  top: 8,
  right: 16,
  left: 8,
  bottom: 36,
} as const;

export const TREND_Y_AXIS_WIDTH = 56;
export const TREND_SYNC_ID = "volume-trend-sync";

function getRate(
  value: number | null | undefined,
  numerator?: number | null,
  denominator?: number | null,
) {
  if (value !== null && value !== undefined) return value;
  if (!numerator || !denominator) return null;
  return (numerator / denominator) * 100;
}

export function buildTrendChartData(
  data: VolumeTrendSeries,
  referenceDate?: string,
): TrendChartPoint[] {
  const isWeekdayMode = data.mode === "weekday";
  const isMonthlyMode = data.mode === "monthly";
  const isCategoryMode = isWeekdayMode || isMonthlyMode;

  return data.dates.map((shortDate, index) => {
    const totalVolume = data.totalVolume[index] ?? null;
    const dispatchVolume = data.dispatchVolume[index] ?? null;
    const arrivalVolume = data.arrivalVolume[index] ?? null;
    const nationalVolume = data.nationalVolume[index] ?? null;

    if (isCategoryMode) {
      const label = data.labels?.[index] ?? shortDate;
      const countText = data.sampleCounts?.[index]
        ? isMonthlyMode
          ? `(${data.sampleCounts[index]}일)`
          : `(${data.sampleCounts[index]}일)`
        : "";
      return {
        axisLabel: `${label}${countText}`,
        dateText: label,
        weekdayText: countText,
        totalVolume,
        dispatchVolume,
        arrivalVolume,
        nationalVolume,
        totalProcessingRate: getRate(data.totalProcessingRate?.[index], totalVolume, nationalVolume),
        dispatchProcessingRate: getRate(data.dispatchProcessingRate?.[index], dispatchVolume, nationalVolume),
        arrivalProcessingRate: getRate(data.arrivalProcessingRate?.[index], arrivalVolume, nationalVolume),
      };
    }

    const fullDate = resolveTrendDate(data.reportDates?.[index], shortDate, referenceDate);
    const { dateText, weekdayText } = splitShortDateWithWeekday(fullDate);
    return {
      axisLabel: `${dateText}${weekdayText}`,
      dateText,
      weekdayText,
      totalVolume,
      dispatchVolume,
      arrivalVolume,
      nationalVolume,
      totalProcessingRate: getRate(data.totalProcessingRate?.[index], totalVolume, nationalVolume),
      dispatchProcessingRate: getRate(data.dispatchProcessingRate?.[index], dispatchVolume, nationalVolume),
      arrivalProcessingRate: getRate(data.arrivalProcessingRate?.[index], arrivalVolume, nationalVolume),
    };
  });
}

export function getTrendXAxisProps(
  pointCount: number,
  isWeekdayMode: boolean,
  hideAxis = false,
  tickFill?: string,
  isMonthlyMode = false,
) {
  const isCategoryMode = isWeekdayMode || isMonthlyMode;
  const denseAxis = !isCategoryMode && pointCount > 10;
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
    angle: isCategoryMode ? 0 : denseAxis ? -35 : -20,
    textAnchor: isCategoryMode ? ("middle" as const) : ("end" as const),
    height: isCategoryMode ? 36 : 52,
    padding: TREND_X_AXIS_PADDING,
    tick: { fontSize: 11, fill: tickFill },
  };
}
