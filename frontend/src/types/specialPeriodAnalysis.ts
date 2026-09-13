export type SpecialPeriodKpiValue = {
  current: number | null;
  prior: number | null;
  changePercent: number | null;
};

export type SpecialPeriodMeta = {
  id: number;
  periodType: string;
  startDate: string;
  endDate: string;
  note?: string | null;
  lengthDays: number;
  windowStart: string;
  windowEnd: string;
};

export type SpecialPeriodOption = {
  id: number;
  periodType: string;
  startDate: string;
  endDate: string;
  note?: string | null;
};

export type SpecialPeriodVolumePoint = {
  totalCurrent: number | null;
  totalPrior: number | null;
  dispatchCurrent: number | null;
  dispatchPrior: number | null;
  arrivalCurrent: number | null;
  arrivalPrior: number | null;
};

export type SpecialPeriodQuotaPoint = {
  actualCurrent: number | null;
  actualPrior: number | null;
  standardCurrent: number | null;
  standardPrior: number | null;
  complianceCurrent: number | null;
  compliancePrior: number | null;
};

export type SpecialPeriodMachineStreamPoint = {
  deck1VolumeCurrent: number | null;
  deck1VolumePrior: number | null;
  deck2VolumeCurrent: number | null;
  deck2VolumePrior: number | null;
  deck3VolumeCurrent: number | null;
  deck3VolumePrior: number | null;
  deck1ShareCurrent: number | null;
  deck1SharePrior: number | null;
  deck2ShareCurrent: number | null;
  deck2SharePrior: number | null;
  deck3ShareCurrent: number | null;
  deck3SharePrior: number | null;
};

export type SpecialPeriodPoint = {
  offset: number;
  label: string;
  currentDate: string | null;
  priorDate: string | null;
  currentInPeriod: boolean;
  priorInPeriod: boolean;
  volume: SpecialPeriodVolumePoint;
  quota: SpecialPeriodQuotaPoint;
  machineSorting: {
    dispatch: SpecialPeriodMachineStreamPoint;
    arrival: SpecialPeriodMachineStreamPoint;
  };
};

export type SpecialPeriodAnalysis = {
  availablePeriods: SpecialPeriodOption[];
  sameYearPeriods: SpecialPeriodOption[];
  currentPeriod: SpecialPeriodMeta | null;
  priorPeriod: SpecialPeriodMeta | null;
  priorMissing: boolean;
  message: string | null;
  series: SpecialPeriodPoint[];
  kpi: {
    totalVolume: SpecialPeriodKpiValue;
    dispatchVolume: SpecialPeriodKpiValue;
    arrivalVolume: SpecialPeriodKpiValue;
    quotaActual: SpecialPeriodKpiValue;
    quotaStandard: SpecialPeriodKpiValue;
    quotaComplianceRate: SpecialPeriodKpiValue;
    machineShare: {
      dispatch: {
        deck1: SpecialPeriodKpiValue;
        deck2: SpecialPeriodKpiValue;
        deck3: SpecialPeriodKpiValue;
      };
      arrival: {
        deck1: SpecialPeriodKpiValue;
        deck2: SpecialPeriodKpiValue;
        deck3: SpecialPeriodKpiValue;
      };
    };
  } | null;
};
