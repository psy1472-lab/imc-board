export type VolumeTrendSeries = {
  mode?: "weekday" | "monthly";
  year?: number;
  labels?: string[];
  months?: string[];
  reportDates: string[];
  dates: string[];
  totalVolume: Array<number | null>;
  dispatchVolume: Array<number | null>;
  arrivalVolume: Array<number | null>;
  nationalVolume: Array<number | null>;
  totalProcessingRate?: Array<number | null>;
  dispatchProcessingRate?: Array<number | null>;
  arrivalProcessingRate?: Array<number | null>;
  sampleCounts?: number[];
};

export type VolumeTrendView = "7d" | "30d" | "weekday";

export type VolumeYearToDate = {
  year: number;
  startDate: string;
  endDate: string;
  dayCount: number;
  nationalVolume?: number | null;
  totalVolume?: number | null;
  dispatchVolume?: number | null;
  arrivalVolume?: number | null;
  avgNationalVolume?: number | null;
  avgTotalVolume?: number | null;
  avgDispatchVolume?: number | null;
  avgArrivalVolume?: number | null;
  processingRate?: number | null;
};
export type VolumeAnalysis = {
  meta: {
    reportDate: string;
    centerName?: string;
    reportFormat?: string | null;
    dayType?: string | null;
  };
  summary: {
    nationalVolume?: number | null;
    totalVolume?: number | null;
    dispatchVolume?: number | null;
    arrivalVolume?: number | null;
    remainingVolume?: number | null;
    processingRate?: number | null;
  };
  benchmarks: {
    prevDay: {
      totalVolume?: number | null;
      dispatchVolume?: number | null;
      arrivalVolume?: number | null;
    };
    avg7d: {
      totalVolume?: number | null;
      dispatchVolume?: number | null;
      arrivalVolume?: number | null;
    };
    avg30d: {
      totalVolume?: number | null;
      dispatchVolume?: number | null;
      arrivalVolume?: number | null;
    };
    sameWeekday: {
      weekdayLabel?: string;
      sampleCount?: number;
      totalVolume?: number | null;
      dispatchVolume?: number | null;
      arrivalVolume?: number | null;
    };
  };
  trends?: {
    "7d": VolumeTrendSeries;
    "30d": VolumeTrendSeries;
    weekday: VolumeTrendSeries;
  };
  yearToDate: VolumeYearToDate;
  priorYearToDate?: VolumeYearToDate | null;
  monthlyTrend: VolumeTrendSeries;
  dailyTrend: VolumeTrendSeries;
};
