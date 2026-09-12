import type { MachineSorting } from "./equipmentAnalysis";

export type CompareInfo = {
  percent?: number | null;
  trend?: string;
  compareValue?: number | null;
  minutes?: number;
};

export type KpiItem = {
  key: string;
  label: string;
  value: number | string | null;
  unit?: string;
  compare?: CompareInfo | null;
  status?: string;
  statusLabel?: string;
};

export type DashboardSummary = {
  meta: {
    reportDate: string;
    centerName?: string;
    reportFormat?: string | null;
    dayType?: string | null;
    communicationStatus: string;
    communicationStatusLabel: string;
    compareBasis: string;
  };
  kpis: KpiItem[];
  hourlyVolume: {
    slots: string[];
    current: Array<{
      slot: string;
      label?: string;
      dispatch?: number | null;
      arrival?: number | null;
      total?: number | null;
    }>;
    peak?: { slot?: string | null; value?: number | null };
  };
  hourlyStaff: {
    slots: string[];
    actualStaff: Array<{ slot: string; label?: string; value?: number | null }>;
    productivity: Array<{ slot: string; label?: string; value?: number | null }>;
    peakStaff?: { slot?: string | null; value?: number | null };
  };
  anomalies: Array<{ severity: string; category: string; message: string }>;
  equipment: {
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
  trend7d: {
    dates: string[];
    totalVolume: Array<number | null>;
    ipsRate: Array<number | null>;
    rejectRate: Array<number | null>;
  };
  machineSorting?: MachineSorting;
  transport: {
    quarter: { actual?: number | null; standard?: number | null; complianceRate?: number | null };
    exchange: { actual?: number | null; standard?: number | null; complianceRate?: number | null };
    exchangeRemaining?: number | null;
  };
  quotaOverages: Array<{
    office: string;
    vehiclesActual?: number | null;
    vehiclesQuota?: number | null;
    difference?: number | null;
    arrivalTime?: string | null;
    status?: string | null;
  }>;
  officeArrivals: Array<{
    office: string;
    arrivalTime?: string | null;
    status?: string | null;
    vehiclesActual?: number | null;
    vehiclesQuota?: number | null;
    difference?: number | null;
    delayMinutes?: number | null;
  }>;
  safety: {
    categories: Array<{ key: string; label: string; passed: number; total: number; status: string }>;
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
};
