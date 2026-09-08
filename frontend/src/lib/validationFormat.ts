import { formatThousandUnit } from "./numberFormat";
import type { ValidationLogEntry } from "../types/reports";

export const VALIDATION_RULE_LABELS: Record<string, string> = {
  dispatch_plus_arrival_equals_total: "발송 + 도착 = 총 처리물량",
  hourly_sum_equals_total: "시간대별 합계 = 일일 처리물량",
  sorted_lte_supply: "구분수 ≤ 공급수",
};

export const VALIDATION_STATUS_LABELS: Record<string, string> = {
  PASS: "통과",
  WARNING: "주의",
  FAIL: "실패",
};

export type ValidationFilter = "all" | "clean" | "warning" | "fail";

export type RawValidationEntry = {
  rule_name?: string;
  ruleName?: string;
  status: string;
  details?: unknown;
};

export function normalizeValidationEntry(entry: RawValidationEntry): ValidationLogEntry {
  return {
    ruleName: entry.ruleName ?? entry.rule_name ?? "unknown",
    status: entry.status,
    details: entry.details,
  };
}

export function getValidationSeverity(
  logs: Array<ValidationLogEntry | RawValidationEntry>,
): "PASS" | "WARNING" | "FAIL" {
  const normalized = logs.map((item) =>
    "ruleName" in item && item.ruleName ? (item as ValidationLogEntry) : normalizeValidationEntry(item),
  );
  if (normalized.some((item) => item.status === "FAIL")) return "FAIL";
  if (normalized.some((item) => item.status === "WARNING")) return "WARNING";
  return "PASS";
}

export function summarizeValidationLogs(
  logs: Array<ValidationLogEntry | RawValidationEntry>,
): string[] {
  const normalized = logs.map((item) =>
    "ruleName" in item && item.ruleName ? (item as ValidationLogEntry) : normalizeValidationEntry(item),
  );
  return normalized
    .filter((item) => item.status !== "PASS")
    .map(
      (item) =>
        `${getValidationRuleLabel(item.ruleName)}: ${VALIDATION_STATUS_LABELS[item.status] ?? item.status}`,
    );
}

export function getReportValidationStatus(report: {
  validationFailCount?: number;
  validationWarningCount?: number;
  validationIssues?: number;
}): "PASS" | "WARNING" | "FAIL" {
  if ((report.validationFailCount ?? 0) > 0) return "FAIL";
  if ((report.validationWarningCount ?? 0) > 0) return "WARNING";
  if ((report.validationIssues ?? 0) > 0) return "WARNING";
  return "PASS";
}

export function matchesValidationFilter(
  report: {
    validationFailCount?: number;
    validationWarningCount?: number;
    validationIssues?: number;
  },
  filter: ValidationFilter,
): boolean {
  const status = getReportValidationStatus(report);
  switch (filter) {
    case "clean":
      return status === "PASS";
    case "warning":
      return status === "WARNING";
    case "fail":
      return status === "FAIL";
    default:
      return true;
  }
}

function formatNumber(value: unknown) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return formatThousandUnit(value) || String(value);
  return String(value);
}

export function formatValidationDetails(ruleName: string, details: unknown): string {
  if (!details || typeof details !== "object") return "-";
  const record = details as Record<string, unknown>;

  switch (ruleName) {
    case "dispatch_plus_arrival_equals_total":
      return `발송 ${formatNumber(record.dispatch)} + 도착 ${formatNumber(record.arrival)} = ${formatNumber(record.expected)} (보고 총량 ${formatNumber(record.total)})`;
    case "hourly_sum_equals_total":
      return `시간대 합계 ${formatNumber(record.hourly_total)} / 일일 총량 ${formatNumber(record.total)}`;
    case "sorted_lte_supply":
      return `구분수 ${formatNumber(record.sorted)} / 공급수 ${formatNumber(record.supply)}`;
    default:
      return JSON.stringify(details);
  }
}

export function getValidationRuleLabel(ruleName: string) {
  return VALIDATION_RULE_LABELS[ruleName] ?? ruleName;
}

export function countValidationIssues(logs: ValidationLogEntry[]) {
  return logs.filter((item) => item.status !== "PASS").length;
}
