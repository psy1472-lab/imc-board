export type StaffingTrendSeries = {
  mode?: "weekday";
  labels?: string[];
  reportDates: string[];
  dates: string[];
  productivity: Array<number | null>;
  volume: Array<number | null>;
  avgStaff: Array<number | null>;
  peakStaff: Array<number | null>;
  sampleCounts?: number[];
};

export type StaffingTrendView = "7d" | "30d" | "weekday";

export type StaffingBenchmark = {
  productivity?: number | null;
  avgStaff?: number | null;
  peakStaff?: number | null;
  weekdayLabel?: string;
  sampleCount?: number;
};

export type StaffingAnalysis = {
  meta: {
    reportDate: string;
    centerName?: string;
  };
  summary: {
    productivity?: number | null;
    avgStaff?: number | null;
    peakStaff?: number | null;
    peakHour?: string | null;
    peakHourVolume?: number | null;
    totalVolume?: number | null;
  };
  hourly: {
    slots: string[];
    labels: string[];
    volume: Array<number | null>;
    staff: Array<number | null>;
    productivity: Array<number | null>;
  };
  benchmarks: {
    prevDay: StaffingBenchmark;
    avg7d: StaffingBenchmark;
    avg30d: StaffingBenchmark;
    sameWeekday: StaffingBenchmark;
  };
  trends?: {
    "7d": StaffingTrendSeries;
    "30d": StaffingTrendSeries;
    weekday: StaffingTrendSeries;
  };
  dailyTrend: StaffingTrendSeries;
};
