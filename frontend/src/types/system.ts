export type SystemStatus = {
  dbPath: string;
  dbExists: boolean;
  dbSizeBytes: number;
  reportCount: number;
  earliestDate: string | null;
  latestDate: string | null;
  validationIssues: number;
  anomalyCount: number;
  thresholdCount: number;
};

export type ThresholdConfig = {
  metricName: string;
  cautionMin: number | null;
  cautionMax: number | null;
  warningMin: number | null;
  warningMax: number | null;
  criticalMin: number | null;
  criticalMax: number | null;
};
