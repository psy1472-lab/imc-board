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
  machineSorting?: MachineSorting;
  machineSortingTrends?: {
    "7d": MachineSortingTrendSeries;
    "30d": MachineSortingTrendSeries;
    weekday: MachineSortingTrendSeries;
  };
};

export type MachineSortingDeck = {
  deck: number;
  volume?: number | null;
  shareRate?: number | null;
};

export type MachineSorting = {
  dispatch: MachineSortingDeck[];
  arrival: MachineSortingDeck[];
};

export type MachineSortingStream = "dispatch" | "arrival";

export type MachineSortingStreamTrend = {
  deck1Volume: Array<number | null>;
  deck2Volume: Array<number | null>;
  deck3Volume: Array<number | null>;
  deck1Share: Array<number | null>;
  deck2Share: Array<number | null>;
  deck3Share: Array<number | null>;
};

export type MachineSortingTrendSeries = {
  mode?: "weekday";
  labels?: string[];
  reportDates: string[];
  dates: string[];
  sampleCounts?: number[];
  dispatch: MachineSortingStreamTrend;
  arrival: MachineSortingStreamTrend;
};
