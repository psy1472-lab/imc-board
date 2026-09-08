export type SafetyTrendSeries = {
  mode?: "weekday";
  labels?: string[];
  reportDates: string[];
  dates: string[];
  incidentCount: Array<number | null>;
  warningCount: Array<number | null>;
  safetyPassRate: Array<number | null>;
  sampleCounts?: number[];
};

export type SafetyTrendView = "7d" | "30d" | "weekday";

export type SafetyBenchmark = {
  incidentCount?: number | null;
  warningCount?: number | null;
  safetyPassRate?: number | null;
  weekdayLabel?: string;
  sampleCount?: number;
};

export type SafetyAnomaly = {
  severity: string;
  category: string;
  categoryLabel?: string;
  message: string;
  source?: string;
};

export type SafetyAnalysis = {
  meta: {
    reportDate: string;
    centerName?: string;
  };
  summary: {
    categoryCount?: number | null;
    passedCategoryCount?: number | null;
    incidentCount?: number | null;
    warningAnomalyCount?: number | null;
    criticalAnomalyCount?: number | null;
    safetyPassRate?: number | null;
    overallStatus?: string;
    overallLabel?: string;
  };
  safety: {
    categories: Array<{
      key: string;
      label: string;
      passed: number;
      total: number;
      status: string;
    }>;
    incidentCount: number;
    incidents: Array<{
      department?: string | null;
      name?: string | null;
      gender?: string | null;
      occurrenceTime?: string | null;
      injuryType?: string | null;
      description?: string | null;
      summary?: string | null;
    }>;
  };
  anomalies: SafetyAnomaly[];
  benchmarks: {
    prevDay: SafetyBenchmark;
    avg7d: SafetyBenchmark;
    avg30d: SafetyBenchmark;
    sameWeekday: SafetyBenchmark;
  };
  trends?: {
    "7d": SafetyTrendSeries;
    "30d": SafetyTrendSeries;
    weekday: SafetyTrendSeries;
  };
  dailyTrend: SafetyTrendSeries;
};
