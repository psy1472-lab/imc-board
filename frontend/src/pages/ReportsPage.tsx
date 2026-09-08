import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { ValidationStatusBadge } from "../components/header/ValidationStatusBadge";
import { OperationPeriodPanel } from "../components/panels/OperationPeriodPanel";
import {
  deleteReport,
  fetchDailyBriefing,
  fetchDashboardSummary,
  fetchReportValidation,
  fetchReports,
  reportFileUrl,
  uploadReport,
} from "../lib/api";
import { downloadCsv, downloadJson } from "../lib/download";
import { formatDateWithWeekday } from "../lib/dateFormat";
import { formatReportFormat } from "../lib/reportFormat";
import {
  VALIDATION_STATUS_LABELS,
  type ValidationFilter,
  countValidationIssues,
  formatValidationDetails,
  getReportValidationStatus,
  getValidationRuleLabel,
  getValidationSeverity,
  matchesValidationFilter,
  normalizeValidationEntry,
  summarizeValidationLogs,
} from "../lib/validationFormat";
import { severityColor } from "../styles/theme";
import type { ReportMetadata, UploadReportResult, ValidationLogEntry } from "../types/reports";

const PAGE_SIZE = 10;

type FormatFilter = "all" | "standard" | "compact";

type UploadSummaryItem = {
  fileName: string;
  reportDate: string;
  severity: "PASS" | "WARNING" | "FAIL";
  issues: string[];
};

type UploadBatchResult = {
  total: number;
  succeeded: number;
  failed: number;
  validationFail: number;
  validationWarning: number;
  skippedNonPdf: number;
  failures: Array<{ file: string; error: string }>;
};

function formatIngestedAt(value: string) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR");
}

function actionButtonStyle(palette: ReturnType<typeof useTheme>["palette"]) {
  return {
    padding: "6px 10px",
    borderRadius: 8,
    border: `1px solid ${palette.border}`,
    background: palette.inputBg,
    color: palette.text,
    fontSize: 12,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
  };
}

function matchesDateRange(reportDate: string, startDate: string, endDate: string): boolean {
  if (startDate && reportDate < startDate) return false;
  if (endDate && reportDate > endDate) return false;
  return true;
}

function isPdfFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || file.type === "application/pdf";
}

function buildVisiblePages(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }
  const pages: (number | "ellipsis")[] = [1];
  const left = Math.max(2, current - 1);
  const right = Math.min(total - 1, current + 1);
  if (left > 2) pages.push("ellipsis");
  for (let pageNumber = left; pageNumber <= right; pageNumber += 1) {
    pages.push(pageNumber);
  }
  if (right < total - 1) pages.push("ellipsis");
  pages.push(total);
  return pages;
}

function validationBadgeLabel(report: ReportMetadata) {
  const status = getReportValidationStatus(report);
  if (status === "PASS") return "검증 정상";
  if (status === "FAIL") {
    return `검증 실패 ${report.validationFailCount ?? report.validationIssues}`;
  }
  return `검증 주의 ${report.validationWarningCount ?? report.validationIssues}`;
}

export default function ReportsPage() {
  const { palette } = useTheme();
  const { selectedDate, compare, refreshDates } = useDashboardFilters();
  const [reports, setReports] = useState<ReportMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{
    current: number;
    total: number;
    fileName: string;
  } | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [selectedReportDates, setSelectedReportDates] = useState<Set<string>>(() => new Set());
  const [validationModal, setValidationModal] = useState<{
    reportDate: string;
    logs: ValidationLogEntry[];
  } | null>(null);
  const [loadingValidation, setLoadingValidation] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [validationFilter, setValidationFilter] = useState<ValidationFilter>("all");
  const [formatFilter, setFormatFilter] = useState<FormatFilter>("all");
  const [dateRangeStart, setDateRangeStart] = useState("");
  const [dateRangeEnd, setDateRangeEnd] = useState("");
  const [uploadSummary, setUploadSummary] = useState<UploadSummaryItem[] | null>(null);
  const [uploadBatchResult, setUploadBatchResult] = useState<UploadBatchResult | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasDateRangeSearch = Boolean(dateRangeStart || dateRangeEnd);
  const dateRangeInvalid = Boolean(dateRangeStart && dateRangeEnd && dateRangeStart > dateRangeEnd);

  const sortedReports = useMemo(
    () => [...reports].sort((a, b) => b.reportDate.localeCompare(a.reportDate)),
    [reports],
  );
  const filteredReports = useMemo(
    () =>
      sortedReports.filter((report) => {
        if (!matchesValidationFilter(report, validationFilter)) return false;
        if (formatFilter !== "all" && report.format !== formatFilter) return false;
        if (hasDateRangeSearch) {
          if (dateRangeInvalid) return false;
          if (!matchesDateRange(report.reportDate, dateRangeStart, dateRangeEnd)) return false;
        }
        return true;
      }),
    [sortedReports, validationFilter, formatFilter, hasDateRangeSearch, dateRangeInvalid, dateRangeStart, dateRangeEnd],
  );
  const filterCounts = useMemo(
    () => ({
      all: sortedReports.length,
      clean: sortedReports.filter((report) => matchesValidationFilter(report, "clean")).length,
      warning: sortedReports.filter((report) => matchesValidationFilter(report, "warning")).length,
      fail: sortedReports.filter((report) => matchesValidationFilter(report, "fail")).length,
    }),
    [sortedReports],
  );
  const totalPages = Math.max(1, Math.ceil(filteredReports.length / PAGE_SIZE));
  const paginatedReports = filteredReports.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const hasMore = page < totalPages;
  const rangeStart = filteredReports.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, filteredReports.length);
  const visiblePages = useMemo(() => buildVisiblePages(page, totalPages), [page, totalPages]);

  useEffect(() => {
    setPage(1);
  }, [validationFilter, formatFilter, dateRangeStart, dateRangeEnd]);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  useEffect(() => {
    setSelectedReportDates((current) => {
      const validDates = new Set(reports.map((report) => report.reportDate));
      const next = new Set([...current].filter((reportDate) => validDates.has(reportDate)));
      return next.size === current.size ? current : next;
    });
  }, [reports]);

  const toggleReportSelection = (reportDate: string) => {
    setSelectedReportDates((current) => {
      const next = new Set(current);
      if (next.has(reportDate)) {
        next.delete(reportDate);
      } else {
        next.add(reportDate);
      }
      return next;
    });
  };

  const allPageSelected =
    paginatedReports.length > 0 &&
    paginatedReports.every((report) => selectedReportDates.has(report.reportDate));

  const toggleSelectAllOnPage = () => {
    setSelectedReportDates((current) => {
      const next = new Set(current);
      if (allPageSelected) {
        paginatedReports.forEach((report) => next.delete(report.reportDate));
      } else {
        paginatedReports.forEach((report) => next.add(report.reportDate));
      }
      return next;
    });
  };

  const selectedReports = useMemo(
    () => reports.filter((report) => selectedReportDates.has(report.reportDate)),
    [reports, selectedReportDates],
  );

  const panelStyle = {
    background: palette.panel,
    border: `1px solid ${palette.border}`,
    borderRadius: 14,
    padding: 16,
  };

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchReports();
      setReports(items);
    } catch {
      setError("보고서 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleUpload = async (files: FileList | File[] | null | undefined) => {
    const selected = Array.from(files ?? []);
    const pdfFiles = selected.filter(isPdfFile);
    const skippedCount = selected.length - pdfFiles.length;

    if (pdfFiles.length === 0) {
      setMessage(null);
      setError(
        selected.length === 0
          ? "선택된 파일이 없습니다."
          : "PDF 파일만 업로드할 수 있습니다. (.pdf 확장자)",
      );
      return;
    }

    setUploading(true);
    setMessage(null);
    setError(null);
    setUploadProgress(null);
    setUploadSummary(null);
    setUploadBatchResult(null);

    const succeeded: string[] = [];
    const failed: Array<{ file: string; error: string }> = [];
    const uploaded: UploadSummaryItem[] = [];

    for (let index = 0; index < pdfFiles.length; index += 1) {
      const file = pdfFiles[index];
      setUploadProgress({ current: index + 1, total: pdfFiles.length, fileName: file.name });
      try {
        const result: UploadReportResult = await uploadReport(file);
        const logs = result.validation.map(normalizeValidationEntry);
        const severity = getValidationSeverity(logs);
        const issues = summarizeValidationLogs(logs);
        uploaded.push({
          fileName: file.name,
          reportDate: result.reportDate,
          severity,
          issues,
        });
        succeeded.push(formatDateWithWeekday(result.reportDate));
      } catch (uploadError) {
        failed.push({
          file: file.name,
          error: uploadError instanceof Error ? uploadError.message : "업로드 실패",
        });
      }
    }

    setUploadProgress(null);
    setUploading(false);

    if (uploaded.length > 0) {
      setUploadSummary(uploaded);
    }

    if (succeeded.length > 0) {
      await Promise.all([loadReports(), refreshDates()]);
    }

    const failCount = uploaded.filter((item) => item.severity === "FAIL").length;
    const warnCount = uploaded.filter((item) => item.severity === "WARNING").length;

    setUploadBatchResult({
      total: pdfFiles.length,
      succeeded: succeeded.length,
      failed: failed.length,
      validationFail: failCount,
      validationWarning: warnCount,
      skippedNonPdf: skippedCount,
      failures: failed,
    });

    if (failed.length === 0) {
      if (failCount > 0) {
        setError(`수집은 완료됐지만 검증 실패 ${failCount}건이 있습니다. 아래 요약을 확인하세요.`);
      } else if (warnCount > 0) {
        setMessage(
          pdfFiles.length === 1
            ? `${succeeded[0]} 보고서가 수집되었습니다. 검증 주의 ${warnCount}건 — 아래 요약을 확인하세요.`
            : `${succeeded.length}건 수집 완료. 검증 주의 ${warnCount}건 — 아래 요약을 확인하세요.`,
        );
      } else {
        const skippedNote = skippedCount > 0 ? ` (PDF가 아닌 파일 ${skippedCount}건 제외)` : "";
        setMessage(
          pdfFiles.length === 1
            ? `${succeeded[0]} 보고서가 수집되었습니다. 검증 이슈 없음.${skippedNote}`
            : `${succeeded.length}건의 보고서가 수집되었습니다. 검증 이슈 없음.${skippedNote}`,
        );
      }
      return;
    }

    if (succeeded.length === 0) {
      setError(`업로드에 실패했습니다: ${failed.map((item) => item.file).join(", ")}`);
      return;
    }

    setMessage(`${succeeded.length}건 수집 완료. 검증 실패 ${failCount}건, 주의 ${warnCount}건.`);
    setError(`실패 ${failed.length}건: ${failed.map((item) => `${item.file} (${item.error})`).join(" / ")}`);
  };

  const handleExportBriefing = async (reportDate: string) => {
    setExporting(`briefing-${reportDate}`);
    try {
      const data = await fetchDailyBriefing(reportDate, compare);
      downloadJson(`imc-briefing-${reportDate}.json`, data);
    } catch {
      setError("브리핑 JSON보내기에 실패했습니다.");
    } finally {
      setExporting(null);
    }
  };

  const handleExportSummary = async (reportDate: string) => {
    setExporting(`summary-${reportDate}`);
    try {
      const data = await fetchDashboardSummary(reportDate, compare);
      downloadJson(`imc-summary-${reportDate}.json`, data);
    } catch {
      setError("대시보드 요약 JSON보내기에 실패했습니다.");
    } finally {
      setExporting(null);
    }
  };

  const handleDeleteSelectedReports = async () => {
    if (selectedReports.length === 0) return;

    const includesUploadedFile = selectedReports.some((report) => report.canDeleteFile);
    const fileNotice = includesUploadedFile
      ? "\n업로드된 PDF 파일도 함께 삭제됩니다."
      : "";
    const confirmed = window.confirm(
      `선택한 ${selectedReports.length}건의 보고서를 삭제하시겠습니까?\nDB의 분석 데이터가 삭제됩니다.${fileNotice}`,
    );
    if (!confirmed) return;

    setDeleting(true);
    setMessage(null);
    setError(null);

    const succeeded: string[] = [];
    const failed: string[] = [];

    for (const report of selectedReports) {
      try {
        await deleteReport(report.reportDate, report.canDeleteFile);
        succeeded.push(report.reportDate);
      } catch {
        failed.push(report.reportDate);
      }
    }

    setSelectedReportDates((current) => {
      const next = new Set(current);
      succeeded.forEach((reportDate) => next.delete(reportDate));
      return next;
    });
    setDeleting(false);

    if (succeeded.length > 0) {
      await Promise.all([loadReports(), refreshDates()]);
      setMessage(`${succeeded.length}건의 보고서를 삭제했습니다.`);
    }
    if (failed.length > 0) {
      setError(`삭제 실패 ${failed.length}건: ${failed.map((date) => formatDateWithWeekday(date)).join(", ")}`);
    }
  };

  const deleteButtonStyle = {
    ...actionButtonStyle(palette),
    color: palette.critical,
    borderColor: palette.critical,
  };

  const handleDownloadUploadFailures = () => {
    if (!uploadBatchResult || uploadBatchResult.failures.length === 0) return;
    const stamp = new Date().toISOString().slice(0, 10);
    downloadCsv(
      `imc-upload-failures-${stamp}.csv`,
      [
        ["파일명", "오류"],
        ...uploadBatchResult.failures.map((item) => [item.file, item.error]),
      ],
    );
  };

  const openValidationDetail = async (reportDate: string) => {
    setLoadingValidation(reportDate);
    setError(null);
    try {
      const logs = await fetchReportValidation(reportDate);
      setValidationModal({ reportDate, logs });
    } catch {
      setError("검증 상세를 불러오지 못했습니다.");
    } finally {
      setLoadingValidation(null);
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={panelStyle}>
        <h2 style={{ margin: "0 0 8px", fontSize: 22 }}>보고서·다운로드</h2>
        <p style={{ margin: 0, color: palette.muted, fontSize: 14 }}>
          PDF 업로드, 수집 보고서 목록과 원본·분석 데이터 다운로드를 제공합니다.
        </p>
      </div>

      <OperationPeriodPanel />

      {message ? (
        <div style={{ ...panelStyle, color: palette.normal, borderColor: palette.normal }}>
          {message}
        </div>
      ) : null}
      {error ? (
        <div style={{ ...panelStyle, color: palette.critical, borderColor: palette.critical }}>
          {error}
        </div>
      ) : null}

      {uploadBatchResult ? (
        <div
          style={{
            ...panelStyle,
            borderColor: uploadBatchResult.failed > 0 ? palette.critical : palette.normal,
            background: palette.panelAlt,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div>
              <h3 style={{ margin: "0 0 10px", fontSize: 16 }}>업로드 결과 요약</h3>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 14 }}>
                <span>전체 {uploadBatchResult.total}건</span>
                <span style={{ color: palette.normal }}>성공 {uploadBatchResult.succeeded}건</span>
                {uploadBatchResult.failed > 0 ? (
                  <span style={{ color: palette.critical }}>실패 {uploadBatchResult.failed}건</span>
                ) : null}
                {uploadBatchResult.validationWarning > 0 ? (
                  <span style={{ color: palette.warning }}>검증 주의 {uploadBatchResult.validationWarning}건</span>
                ) : null}
                {uploadBatchResult.validationFail > 0 ? (
                  <span style={{ color: palette.critical }}>검증 실패 {uploadBatchResult.validationFail}건</span>
                ) : null}
                {uploadBatchResult.skippedNonPdf > 0 ? (
                  <span style={{ color: palette.muted }}>
                    PDF 제외 {uploadBatchResult.skippedNonPdf}건
                  </span>
                ) : null}
              </div>
            </div>
            {uploadBatchResult.failures.length > 0 ? (
              <button
                type="button"
                onClick={handleDownloadUploadFailures}
                style={{
                  ...actionButtonStyle(palette),
                  fontWeight: 600,
                  borderColor: palette.critical,
                  color: palette.critical,
                }}
              >
                실패 목록 CSV 다운로드
              </button>
            ) : null}
          </div>
          {uploadBatchResult.failures.length > 0 ? (
            <ul style={{ margin: "12px 0 0", paddingLeft: 18, color: palette.muted, fontSize: 12, lineHeight: 1.7 }}>
              {uploadBatchResult.failures.map((item) => (
                <li key={item.file}>
                  <strong style={{ color: palette.text }}>{item.file}</strong> — {item.error}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {uploadSummary && uploadSummary.length > 0 ? (
        <div style={panelStyle}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>업로드 검증 요약</h3>
          <div style={{ display: "grid", gap: 10 }}>
            {uploadSummary.map((item) => (
              <div
                key={`${item.reportDate}-${item.fileName}`}
                style={{
                  border: `1px solid ${palette.border}`,
                  borderLeft: `4px solid ${severityColor(item.severity === "FAIL" ? "CRITICAL" : item.severity, palette)}`,
                  borderRadius: 10,
                  padding: "12px 14px",
                  background: palette.panelAlt,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    alignItems: "center",
                    flexWrap: "wrap",
                    marginBottom: item.issues.length > 0 ? 8 : 0,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{formatDateWithWeekday(item.reportDate)}</div>
                    <div style={{ color: palette.muted, fontSize: 12, marginTop: 4 }}>{item.fileName}</div>
                  </div>
                  <ValidationStatusBadge
                    label={
                      item.severity === "PASS"
                        ? "검증 통과"
                        : item.severity === "FAIL"
                          ? "검증 실패"
                          : "검증 주의"
                    }
                    status={item.severity}
                    onClick={() => void openValidationDetail(item.reportDate)}
                  />
                </div>
                {item.issues.length > 0 ? (
                  <ul style={{ margin: 0, paddingLeft: 18, color: palette.muted, fontSize: 12, lineHeight: 1.7 }}>
                    {item.issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ color: palette.muted, fontSize: 12 }}>모든 검증 규칙을 통과했습니다.</div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div style={panelStyle}>
        <h3 style={{ marginTop: 0 }}>PDF 업로드</h3>
        <p style={{ color: palette.muted, fontSize: 13, marginTop: 0 }}>
          일일소통현황 PDF를 하나 또는 여러 개 선택해 업로드하면 자동 파싱 후 DB에 저장됩니다.
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          disabled={uploading}
          onChange={(event) => {
            void handleUpload(event.target.files);
            event.target.value = "";
          }}
          style={{ display: "none" }}
        />
        <div
          role="button"
          tabIndex={0}
          onClick={() => {
            if (!uploading) fileInputRef.current?.click();
          }}
          onKeyDown={(event) => {
            if ((event.key === "Enter" || event.key === " ") && !uploading) {
              event.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          onDragEnter={(event) => {
            event.preventDefault();
            if (!uploading) setDragActive(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            if (!uploading) setDragActive(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              setDragActive(false);
            }
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragActive(false);
            if (!uploading) void handleUpload(event.dataTransfer.files);
          }}
          style={{
            border: `2px dashed ${dragActive ? palette.caution : palette.border}`,
            borderRadius: 12,
            padding: "28px 20px",
            textAlign: "center",
            background: dragActive ? `${palette.caution}14` : palette.panelAlt,
            cursor: uploading ? "not-allowed" : "pointer",
            opacity: uploading ? 0.7 : 1,
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
            {uploading ? "업로드·파싱 중..." : "PDF 파일을 여기에 놓거나 클릭해 선택"}
          </div>
          <div style={{ color: palette.muted, fontSize: 13, marginBottom: 14 }}>
            여러 파일을 한 번에 선택할 수 있습니다.
          </div>
          <button
            type="button"
            disabled={uploading}
            onClick={(event) => {
              event.stopPropagation();
              fileInputRef.current?.click();
            }}
            style={{
              ...actionButtonStyle(palette),
              padding: "10px 18px",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            PDF 파일 선택
          </button>
        </div>
        {uploading ? (
          <div style={{ marginTop: 10, color: palette.muted }}>
            {uploadProgress
              ? `업로드·파싱 중 (${uploadProgress.current}/${uploadProgress.total}) ${uploadProgress.fileName}`
              : "업로드·파싱 중..."}
          </div>
        ) : null}
      </div>

      <div style={panelStyle}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 12,
            gap: 12,
          }}
        >
          <h3 style={{ margin: 0 }}>
            수집된 보고서
            {reports.length > 0 ? (
              <span style={{ color: palette.muted, fontSize: 13, fontWeight: 400, marginLeft: 8 }}>
                전체 {reports.length}건
              </span>
            ) : null}
          </h3>
          <button type="button" onClick={() => void loadReports()} style={actionButtonStyle(palette)}>
            새로고침
          </button>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 12,
            flexWrap: "wrap",
          }}
        >
          <label style={{ fontSize: 13, color: palette.muted, whiteSpace: "nowrap" }}>보고일 검색</label>
          <label style={{ fontSize: 13, color: palette.muted, whiteSpace: "nowrap" }}>시작일</label>
          <input
            type="date"
            value={dateRangeStart}
            onChange={(event) => setDateRangeStart(event.target.value)}
            style={{
              padding: "8px 10px",
              background: palette.inputBg,
              color: palette.text,
              border: `1px solid ${dateRangeInvalid ? palette.critical : palette.border}`,
              borderRadius: 8,
              fontSize: 13,
            }}
          />
          <label style={{ fontSize: 13, color: palette.muted, whiteSpace: "nowrap" }}>최종일</label>
          <input
            type="date"
            value={dateRangeEnd}
            onChange={(event) => setDateRangeEnd(event.target.value)}
            style={{
              padding: "8px 10px",
              background: palette.inputBg,
              color: palette.text,
              border: `1px solid ${dateRangeInvalid ? palette.critical : palette.border}`,
              borderRadius: 8,
              fontSize: 13,
            }}
          />
          {hasDateRangeSearch ? (
            <button
              type="button"
              onClick={() => {
                setDateRangeStart("");
                setDateRangeEnd("");
              }}
              style={actionButtonStyle(palette)}
            >
              검색 초기화
            </button>
          ) : null}
          {hasDateRangeSearch && !dateRangeInvalid ? (
            <span style={{ fontSize: 13, color: palette.muted }}>
              {dateRangeStart ? formatDateWithWeekday(dateRangeStart) : "처음"}
              {" ~ "}
              {dateRangeEnd ? formatDateWithWeekday(dateRangeEnd) : "최신"}
              {" · "}
              {filteredReports.length}건
            </span>
          ) : null}
          {dateRangeInvalid ? (
            <span style={{ fontSize: 12, color: palette.critical }}>시작일은 최종일보다 이후일 수 없습니다.</span>
          ) : null}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          {(
            [
              { value: "all" as ValidationFilter, label: "전체", count: filterCounts.all },
              { value: "clean" as ValidationFilter, label: "정상", count: filterCounts.clean },
              { value: "warning" as ValidationFilter, label: "주의", count: filterCounts.warning },
              { value: "fail" as ValidationFilter, label: "실패", count: filterCounts.fail },
            ] as const
          ).map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setValidationFilter(option.value)}
              style={{
                ...actionButtonStyle(palette),
                fontWeight: validationFilter === option.value ? 700 : 400,
                borderColor:
                  validationFilter === option.value
                    ? option.value === "fail"
                      ? palette.critical
                      : option.value === "warning"
                        ? palette.warning
                        : palette.normal
                    : palette.border,
                color:
                  option.value === "fail" && option.count > 0
                    ? palette.critical
                    : option.value === "warning" && option.count > 0
                      ? palette.warning
                      : palette.text,
              }}
            >
              {option.label} {option.count}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
          {(
            [
              { value: "all" as FormatFilter, label: "형식 전체" },
              { value: "standard" as FormatFilter, label: "평일형" },
              { value: "compact" as FormatFilter, label: "축약형" },
            ] as const
          ).map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setFormatFilter(option.value)}
              style={{
                ...actionButtonStyle(palette),
                fontWeight: formatFilter === option.value ? 700 : 400,
                borderColor: formatFilter === option.value ? palette.caution : palette.border,
              }}
            >
              {option.label}
            </button>
          ))}
        </div>

        {filteredReports.length > 0 ? (
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
              marginBottom: 14,
              flexWrap: "wrap",
            }}
          >
            {selectedReportDates.size > 0 ? (
              <button
                type="button"
                onClick={() => void handleDeleteSelectedReports()}
                disabled={deleting}
                style={{
                  ...deleteButtonStyle,
                  padding: "8px 14px",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {deleting ? "삭제 중..." : `선택 삭제 (${selectedReportDates.size}건)`}
              </button>
            ) : null}
          </div>
        ) : null}

        {loading ? (
          <div style={{ color: palette.muted }}>목록을 불러오는 중...</div>
        ) : reports.length === 0 ? (
          <div style={{ color: palette.muted }}>수집된 보고서가 없습니다.</div>
        ) : filteredReports.length === 0 ? (
          <div style={{ color: palette.muted }}>
            {dateRangeInvalid
              ? "기간 검색 조건을 확인해 주세요."
              : hasDateRangeSearch
                ? "선택한 기간에 해당하는 보고서가 없습니다."
                : "선택한 필터에 맞는 보고서가 없습니다."}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: palette.muted, textAlign: "left" }}>
                  <th style={{ padding: "10px 8px", width: 40 }}>
                    <input
                      type="checkbox"
                      checked={allPageSelected}
                      onChange={toggleSelectAllOnPage}
                      aria-label="현재 페이지 전체 선택"
                    />
                  </th>
                  <th style={{ padding: "10px 8px" }}>보고일</th>
                  <th style={{ padding: "10px 8px" }}>형식</th>
                  <th style={{ padding: "10px 8px" }}>파일</th>
                  <th style={{ padding: "10px 8px" }}>수집 시각</th>
                  <th style={{ padding: "10px 8px" }}>검증</th>
                  <th style={{ padding: "10px 8px" }}>다운로드</th>
                </tr>
              </thead>
              <tbody>
                {paginatedReports.map((report) => {
                  const isSelected = report.reportDate === selectedDate;
                  const validationStatus = getReportValidationStatus(report);
                  return (
                    <tr
                      key={report.reportDate}
                      style={{
                        borderTop: `1px solid ${palette.border}`,
                        background: isSelected ? `${palette.normal}14` : "transparent",
                      }}
                    >
                      <td style={{ padding: "10px 8px" }}>
                        <input
                          type="checkbox"
                          checked={selectedReportDates.has(report.reportDate)}
                          onChange={() => toggleReportSelection(report.reportDate)}
                          aria-label={`${formatDateWithWeekday(report.reportDate)} 선택`}
                        />
                      </td>
                      <td style={{ padding: "10px 8px", fontWeight: isSelected ? 700 : 500 }}>
                        {formatDateWithWeekday(report.reportDate)}
                      </td>
                      <td style={{ padding: "10px 8px" }}>{formatReportFormat(report.format)}</td>
                      <td style={{ padding: "10px 8px" }}>{report.fileName ?? "-"}</td>
                      <td style={{ padding: "10px 8px" }}>{formatIngestedAt(report.ingestedAt)}</td>
                      <td style={{ padding: "10px 8px" }}>
                        {loadingValidation === report.reportDate ? (
                          <span style={{ color: palette.muted, fontSize: 12 }}>불러오는 중...</span>
                        ) : (
                          <ValidationStatusBadge
                            label={validationBadgeLabel(report)}
                            status={validationStatus}
                            onClick={() => void openValidationDetail(report.reportDate)}
                          />
                        )}
                      </td>
                      <td style={{ padding: "10px 8px" }}>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {report.hasFile ? (
                            <a
                              href={reportFileUrl(report.reportDate)}
                              target="_blank"
                              rel="noreferrer"
                              style={{ ...actionButtonStyle(palette), textDecoration: "none" }}
                            >
                              PDF
                            </a>
                          ) : (
                            <span style={{ color: palette.muted, fontSize: 12 }}>PDF 없음</span>
                          )}
                          <button
                            type="button"
                            style={actionButtonStyle(palette)}
                            disabled={exporting === `briefing-${report.reportDate}`}
                            onClick={() => void handleExportBriefing(report.reportDate)}
                          >
                            브리핑 JSON
                          </button>
                          <button
                            type="button"
                            style={actionButtonStyle(palette)}
                            disabled={exporting === `summary-${report.reportDate}`}
                            onClick={() => void handleExportSummary(report.reportDate)}
                          >
                            요약 JSON
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {filteredReports.length > PAGE_SIZE ? (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: 16,
                  padding: "14px 16px",
                  gap: 16,
                  flexWrap: "wrap",
                  borderRadius: 12,
                  border: `1px solid ${palette.border}`,
                  background: palette.panelAlt,
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 160 }}>
                  <span style={{ color: palette.text, fontSize: 14, fontWeight: 600 }}>
                    {rangeStart}–{rangeEnd} / {filteredReports.length}건
                  </span>
                  <span style={{ color: palette.muted, fontSize: 12 }}>
                    {page} / {totalPages} 페이지
                  </span>
                </div>

                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    style={{
                      ...actionButtonStyle(palette),
                      padding: "8px 14px",
                      fontSize: 13,
                      fontWeight: 600,
                      opacity: page === 1 ? 0.45 : 1,
                      cursor: page === 1 ? "not-allowed" : "pointer",
                    }}
                    disabled={page === 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                  >
                    이전
                  </button>
                  {visiblePages.map((pageNumber, index) =>
                    pageNumber === "ellipsis" ? (
                      <span
                        key={`ellipsis-${index}`}
                        style={{ color: palette.muted, fontSize: 14, padding: "0 4px" }}
                      >
                        …
                      </span>
                    ) : (
                      <button
                        key={pageNumber}
                        type="button"
                        style={{
                          ...actionButtonStyle(palette),
                          minWidth: 36,
                          padding: "8px 10px",
                          fontSize: 13,
                          fontWeight: page === pageNumber ? 700 : 500,
                          borderColor: page === pageNumber ? palette.caution : palette.border,
                          background: page === pageNumber ? `${palette.caution}22` : palette.inputBg,
                          color: page === pageNumber ? palette.text : palette.muted,
                        }}
                        onClick={() => setPage(pageNumber)}
                      >
                        {pageNumber}
                      </button>
                    ),
                  )}
                  <button
                    type="button"
                    style={{
                      ...actionButtonStyle(palette),
                      padding: "8px 14px",
                      fontSize: 13,
                      fontWeight: 600,
                      opacity: !hasMore ? 0.45 : 1,
                      cursor: !hasMore ? "not-allowed" : "pointer",
                    }}
                    disabled={!hasMore}
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                  >
                    다음
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {validationModal ? (
        <div
          role="presentation"
          onClick={() => setValidationModal(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.55)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            zIndex: 1000,
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="validation-modal-title"
            onClick={(event) => event.stopPropagation()}
            style={{
              ...panelStyle,
              width: "min(560px, 100%)",
              maxHeight: "80vh",
              overflowY: "auto",
              boxShadow: "0 20px 60px rgba(0, 0, 0, 0.35)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
              <div>
                <h3 id="validation-modal-title" style={{ margin: "0 0 6px", fontSize: 18 }}>
                  검증 상세
                </h3>
                <div style={{ color: palette.muted, fontSize: 13 }}>
                  {formatDateWithWeekday(validationModal.reportDate)}
                  {countValidationIssues(validationModal.logs) > 0
                    ? ` · 이슈 ${countValidationIssues(validationModal.logs)}건`
                    : " · 이슈 없음"}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setValidationModal(null)}
                style={actionButtonStyle(palette)}
              >
                닫기
              </button>
            </div>

            <div style={{ display: "grid", gap: 10 }}>
              {validationModal.logs.map((item) => {
                const statusTone =
                  item.status === "FAIL"
                    ? "CRITICAL"
                    : item.status === "WARNING"
                      ? "WARNING"
                      : "NORMAL";
                return (
                  <div
                    key={item.ruleName}
                    style={{
                      border: `1px solid ${palette.border}`,
                      borderLeft: `4px solid ${severityColor(statusTone, palette)}`,
                      borderRadius: 10,
                      padding: "12px 14px",
                      background: palette.panelAlt,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
                      <div style={{ fontWeight: 600 }}>{getValidationRuleLabel(item.ruleName)}</div>
                      <span style={{ color: severityColor(statusTone, palette), fontSize: 12, fontWeight: 700 }}>
                        {VALIDATION_STATUS_LABELS[item.status] ?? item.status}
                      </span>
                    </div>
                    <div style={{ color: palette.muted, fontSize: 12, lineHeight: 1.6 }}>
                      {formatValidationDetails(item.ruleName, item.details)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
