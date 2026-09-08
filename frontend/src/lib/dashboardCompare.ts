import type { VolumeTrendView } from "../types/volumeAnalysis";

export type CompareBasis = "prev_day" | "7d_avg" | "30d_avg" | "same_weekday";

export const COMPARE_OPTIONS: Array<{ value: CompareBasis; label: string }> = [
  { value: "prev_day", label: "전일" },
  { value: "7d_avg", label: "최근 7업무일 평균" },
  { value: "30d_avg", label: "최근 30업무일 평균" },
  { value: "same_weekday", label: "동일 요일 평균" },
];

export const TREND_OPTIONS: Array<{ value: VolumeTrendView; label: string }> = [
  { value: "7d", label: "최근 7업무일" },
  { value: "30d", label: "최근 30업무일" },
  { value: "weekday", label: "요일별 평균" },
];

export function isCompareBasis(value: string): value is CompareBasis {
  return COMPARE_OPTIONS.some((option) => option.value === value);
}

export function compareToTrendView(compare: CompareBasis): VolumeTrendView | null {
  switch (compare) {
    case "7d_avg":
      return "7d";
    case "30d_avg":
      return "30d";
    case "same_weekday":
      return "weekday";
    default:
      return null;
  }
}

export function trendViewToCompare(trendView: VolumeTrendView): CompareBasis {
  switch (trendView) {
    case "7d":
      return "7d_avg";
    case "30d":
      return "30d_avg";
    case "weekday":
      return "same_weekday";
  }
}

export function compareToBenchmarkKey(
  compare: CompareBasis,
): "prevDay" | "avg7d" | "avg30d" | "sameWeekday" {
  switch (compare) {
    case "prev_day":
      return "prevDay";
    case "7d_avg":
      return "avg7d";
    case "30d_avg":
      return "avg30d";
    case "same_weekday":
      return "sameWeekday";
  }
}
