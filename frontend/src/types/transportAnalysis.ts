export type TransportOfficeRow = {
  office: string;
  volume?: number | null;
  vehiclesActual?: number | null;
  vehiclesQuota?: number | null;
  difference?: number | null;
  arrivalTime?: string | null;
  delayMinutes?: number | null;
  delayed?: boolean | null;
  status?: string | null;
  statusLabel?: string | null;
};

export type TransportTrendSeries = {
  mode?: "weekday";
  labels?: string[];
  reportDates: string[];
  dates: string[];
  quarterComplianceRate: Array<number | null>;
  exchangeComplianceRate: Array<number | null>;
  overageOfficeCount: Array<number | null>;
  sampleCounts?: number[];
};

export type TransportTrendView = "7d" | "30d" | "weekday";

export type TransportBenchmark = {
  quarterComplianceRate?: number | null;
  exchangeComplianceRate?: number | null;
  overageOfficeCount?: number | null;
  weekdayLabel?: string;
  sampleCount?: number;
};

export type TransportAnalysis = {
  meta: {
    reportDate: string;
    centerName?: string;
  };
  summary: {
    quarterActual?: number | null;
    quarterStandard?: number | null;
    quarterComplianceRate?: number | null;
    exchangeActual?: number | null;
    exchangeStandard?: number | null;
    exchangeComplianceRate?: number | null;
    exchangeRemaining?: number | null;
    overageOfficeCount?: number | null;
    overageOfficeVolume?: number | null;
    delayedOfficeCount?: number | null;
    delayedOfficeVolume?: number | null;
    totalOfficeVolume?: number | null;
    officeCount?: number | null;
  };
  offices: TransportOfficeRow[];
  quotaOverages: TransportOfficeRow[];
  benchmarks: {
    prevDay: TransportBenchmark;
    avg7d: TransportBenchmark;
    avg30d: TransportBenchmark;
    sameWeekday: TransportBenchmark;
  };
  trends?: {
    "7d": TransportTrendSeries;
    "30d": TransportTrendSeries;
    weekday: TransportTrendSeries;
  };
  dailyTrend: TransportTrendSeries;
};
