export type ReportMetadata = {
  reportDate: string;
  centerName: string | null;
  format: string | null;
  dayType?: string | null;
  filePath: string | null;
  fileName: string | null;
  ingestedAt: string;
  validationIssues: number;
  validationFailCount?: number;
  validationWarningCount?: number;
  hasFile: boolean;
  canDeleteFile: boolean;
};

export type ValidationLogEntry = {
  ruleName: string;
  status: string;
  details: unknown;
};

export type ReportDateMeta = {
  reportDate: string;
  format?: string | null;
  dayType?: string | null;
};

export type UploadReportResult = {
  reportDate: string;
  centerName: string;
  format: string;
  dayType?: string | null;
  validation: Array<{
    rule_name: string;
    status: string;
    details?: unknown;
  }>;
};
