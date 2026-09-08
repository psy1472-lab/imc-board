export type EquipmentTrendSeries = {
  mode?: "weekday";
  labels?: string[];
  reportDates: string[];
  dates: string[];
  sortingRate: Array<number | null>;
  ipsRate: Array<number | null>;
  rejectRate: Array<number | null>;
  unreadRate: Array<number | null>;
  avgThroughput: Array<number | null>;
  peakThroughput: Array<number | null>;
  sampleCounts?: number[];
};

export type EquipmentTrendView = "7d" | "30d" | "weekday";

export type EquipmentBenchmark = {
  sortingRate?: number | null;
  ipsRate?: number | null;
  rejectRate?: number | null;
  unreadRate?: number | null;
  weekdayLabel?: string;
  sampleCount?: number;
};

export type EquipmentAnalysis = {
  meta: {
    reportDate: string;
    centerName?: string;
  };
  summary: {
    totalSupply?: number | null;
    totalSorted?: number | null;
    sortingRate?: number | null;
    ipsRate?: number | null;
    rejectRate?: number | null;
    shortcutRate?: number | null;
    avgThroughput?: number | null;
    peakThroughput?: number | null;
    unreadCount?: number | null;
    unreadRate?: number | null;
    ipsTarget?: number | null;
  };
  benchmarks: {
    prevDay: EquipmentBenchmark;
    avg7d: EquipmentBenchmark;
    avg30d: EquipmentBenchmark;
    sameWeekday: EquipmentBenchmark;
  };
  trends?: {
    "7d": EquipmentTrendSeries;
    "30d": EquipmentTrendSeries;
    weekday: EquipmentTrendSeries;
  };
  dailyTrend: EquipmentTrendSeries;
};
