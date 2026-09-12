import type { DashboardSummary } from "../types/dashboard";
import type { VolumeAnalysis } from "../types/volumeAnalysis";
import type { StaffingAnalysis } from "../types/staffingAnalysis";
import type { TransportAnalysis } from "../types/transportAnalysis";
import type { EquipmentAnalysis } from "../types/equipmentAnalysis";
import type { SafetyAnalysis } from "../types/safetyAnalysis";
import type { DailyBriefing } from "../types/briefing";
import type {
  ReportDateMeta,
  ReportMetadata,
  UploadReportResult,
  ValidationLogEntry,
} from "../types/reports";
import type { SystemStatus, ThresholdConfig } from "../types/system";
import type { OperationPeriod, OperationPeriodType } from "../types/operationPeriod";
import { adminAuthHeaders } from "./adminToken";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = `${API_BASE}${path}`;
  try {
    return await fetch(url, init);
  } catch {
    if (!API_BASE && import.meta.env.PROD) {
      throw new Error(
        "API 서버에 연결할 수 없습니다. Vercel 환경변수 VITE_API_BASE 또는 /api 프록시 설정을 확인해 주세요.",
      );
    }
    throw new Error("API 서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.");
  }
}

async function readApiError(res: Response, fallback: string): Promise<string> {
  try {
    const detail = await res.json();
    if (typeof detail.detail === "string") return detail.detail;
    if (Array.isArray(detail.detail)) {
      return detail.detail
        .map((item: { msg?: string }) => item.msg)
        .filter(Boolean)
        .join(", ");
    }
  } catch {
    // ignore JSON parse errors
  }
  if (res.status === 503) {
    return "서버가 일시적으로 사용 중입니다. 잠시 후 다시 시도해 주세요.";
  }
  if (res.status >= 500) {
    return "서버 오류가 발생했습니다. 백엔드가 실행 중인지 확인해 주세요.";
  }
  return fallback;
}

export type ReportDateList = {
  dates: string[];
  latestDate: string | null;
  metadata: ReportDateMeta[];
};

export type DashboardHeader = {
  reportDate: string;
  communicationStatus: string;
  communicationStatusLabel: string;
  validationSeverity: "PASS" | "WARNING" | "FAIL";
  validationFailCount: number;
  validationWarningCount: number;
};

export async function fetchReportDateList(): Promise<ReportDateList> {
  const res = await apiFetch("/api/reports/dates");
  if (!res.ok) {
    throw new Error(await readApiError(res, "보고서 날짜를 불러오지 못했습니다."));
  }
  const data = await res.json();
  const dates: string[] = data.dates ?? [];
  return {
    dates,
    latestDate: data.latestDate ?? dates[dates.length - 1] ?? null,
    metadata: data.metadata ?? [],
  };
}

export async function fetchReportDates(): Promise<string[]> {
  const data = await fetchReportDateList();
  return data.dates;
}

export async function fetchReportDateMetadata(): Promise<ReportDateMeta[]> {
  const data = await fetchReportDateList();
  return data.metadata;
}

export async function fetchDashboardHeader(date: string): Promise<DashboardHeader> {
  const res = await apiFetch(`/api/dashboard/header?date=${date}`);
  if (!res.ok) {
    throw new Error(await readApiError(res, "헤더 상태를 불러오지 못했습니다."));
  }
  return res.json();
}

export async function fetchDashboardSummary(
  date: string,
  compare = "prev_day",
): Promise<DashboardSummary> {
  const res = await fetch(
    `${API_BASE}/api/dashboard/summary?date=${date}&compare=${compare}`,
    { cache: "no-cache" },
  );
  if (!res.ok) {
    throw new Error("dashboard summary not found");
  }
  return res.json();
}

export async function fetchVolumeAnalysis(date: string): Promise<VolumeAnalysis> {
  const res = await fetch(`${API_BASE}/api/dashboard/volume?date=${date}`);
  if (!res.ok) {
    throw new Error("volume analysis not found");
  }
  return res.json();
}

export async function fetchStaffingAnalysis(date: string): Promise<StaffingAnalysis> {
  const res = await fetch(`${API_BASE}/api/dashboard/staffing?date=${date}`);
  if (!res.ok) {
    throw new Error("staffing analysis not found");
  }
  return res.json();
}

export async function fetchTransportAnalysis(date: string): Promise<TransportAnalysis> {
  const res = await fetch(`${API_BASE}/api/dashboard/transport?date=${date}`);
  if (!res.ok) {
    throw new Error("transport analysis not found");
  }
  return res.json();
}

export async function fetchEquipmentAnalysis(date: string): Promise<EquipmentAnalysis> {
  const res = await fetch(`${API_BASE}/api/dashboard/equipment?date=${date}`, { cache: "no-cache" });
  if (!res.ok) {
    throw new Error("equipment analysis not found");
  }
  return res.json();
}

export async function fetchSafetyAnalysis(date: string): Promise<SafetyAnalysis> {
  const res = await fetch(`${API_BASE}/api/dashboard/safety?date=${date}`);
  if (!res.ok) {
    throw new Error("safety analysis not found");
  }
  return res.json();
}

export async function fetchDailyBriefing(
  date: string,
  compare = "prev_day",
  sections: "all" | "core" | "forecast" = "all",
): Promise<DailyBriefing> {
  const res = await fetch(
    `${API_BASE}/api/dashboard/briefing?date=${date}&compare=${compare}&sections=${sections}`,
    { cache: "no-cache" },
  );
  if (!res.ok) {
    throw new Error("daily briefing not found");
  }
  return res.json();
}

export async function fetchReports(): Promise<ReportMetadata[]> {
  const res = await fetch(`${API_BASE}/api/reports`);
  const data = await res.json();
  return data.reports ?? [];
}

export async function uploadReport(file: File): Promise<UploadReportResult> {
  const formData = new FormData();
  formData.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/reports/upload`, {
      method: "POST",
      headers: adminAuthHeaders(),
      body: formData,
    });
  } catch {
    throw new Error(
      "API 서버에 연결할 수 없습니다. 백엔드(포트 8001)가 실행 중인지 확인해 주세요.",
    );
  }
  if (!res.ok) {
    throw new Error(await readApiError(res, "PDF 업로드에 실패했습니다."));
  }
  return res.json();
}

export function reportFileUrl(reportDate: string) {
  return `${API_BASE}/api/reports/${reportDate}/file`;
}

export async function deleteReport(
  reportDate: string,
  deleteFile = true,
): Promise<{ deleted: boolean; reportDate: string; fileDeleted: boolean }> {
  const res = await fetch(
    `${API_BASE}/api/reports/${reportDate}?delete_file=${deleteFile ? "true" : "false"}`,
    { method: "DELETE", headers: adminAuthHeaders() },
  );
  if (!res.ok) {
    throw new Error("report delete failed");
  }
  return res.json();
}

export async function fetchReportValidation(reportDate: string): Promise<ValidationLogEntry[]> {
  const res = await fetch(`${API_BASE}/api/reports/${reportDate}/validation`);
  if (!res.ok) {
    throw new Error("validation logs not found");
  }
  const data = await res.json();
  return data.validation ?? [];
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE}/api/system/status`);
  if (!res.ok) {
    throw new Error("system status not found");
  }
  return res.json();
}

export async function fetchThresholds(): Promise<ThresholdConfig[]> {
  const res = await fetch(`${API_BASE}/api/system/thresholds`);
  const data = await res.json();
  return data.thresholds ?? [];
}

export async function updateThreshold(
  metricName: string,
  payload: Partial<ThresholdConfig>,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/system/thresholds/${metricName}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...adminAuthHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error("threshold update failed");
  }
}

export async function fetchOperationPeriods(): Promise<OperationPeriod[]> {
  const res = await fetch(`${API_BASE}/api/operation-periods`);
  if (!res.ok) {
    throw new Error("operation periods not found");
  }
  const data = await res.json();
  return data.periods ?? [];
}

export async function createOperationPeriod(payload: {
  periodType: OperationPeriodType;
  startDate: string;
  endDate?: string;
  note?: string;
}): Promise<OperationPeriod> {
  const res = await fetch(`${API_BASE}/api/operation-periods`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminAuthHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readApiError(res, "운영 특이 일정 저장에 실패했습니다."));
  }
  return res.json();
}

export async function updateOperationPeriod(
  periodId: number,
  payload: {
    periodType: OperationPeriodType;
    startDate: string;
    endDate?: string;
    note?: string;
  },
): Promise<OperationPeriod> {
  const res = await fetch(`${API_BASE}/api/operation-periods/${periodId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...adminAuthHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readApiError(res, "운영 특이 일정 수정에 실패했습니다."));
  }
  return res.json();
}

export async function deleteOperationPeriod(periodId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/operation-periods/${periodId}`, {
    method: "DELETE",
    headers: adminAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(await readApiError(res, "운영 특이 일정 삭제에 실패했습니다."));
  }
}

export async function verifyAdminPassword(password: string): Promise<{ ok: boolean; token: string }> {
  const res = await apiFetch("/api/admin/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: password.trim() }),
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("관리자 비밀번호가 올바르지 않습니다.");
    }
    throw new Error(await readApiError(res, "관리자 인증에 실패했습니다."));
  }
  return res.json();
}
