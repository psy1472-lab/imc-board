import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ValidationStatusBadge } from "../components/header/ValidationStatusBadge";
import { CommunicationStatusBadge } from "../components/header/CommunicationStatusBadge";
import { OperationPeriodBadge } from "../components/header/OperationPeriodBadge";
import { ThemeToggle } from "../components/header/ThemeToggle";
import { ReportDateCalendar } from "../components/filters/ReportDateCalendar";
import { NAV_ITEMS } from "../config/navigation";
import { useAdminAuth } from "../context/AdminAuthContext";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { fetchOperationPeriods, fetchReportValidation } from "../lib/api";
import { COMPARE_OPTIONS } from "../lib/dashboardCompare";
import { formatDateWithWeekday } from "../lib/dateFormat";
import { getActiveOperationPeriods } from "../lib/operationPeriodMatch";
import { getValidationSeverity, summarizeValidationLogs } from "../lib/validationFormat";
import type { OperationPeriod } from "../types/operationPeriod";

export function DashboardLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { palette } = useTheme();
  const { isAdmin, logout } = useAdminAuth();
  const { dates, selectedDate, setSelectedDate, compare, setCompareBasis, error, loadDashboardSummary } =
    useDashboardFilters();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [validationStatus, setValidationStatus] = useState<{
    severity: "PASS" | "WARNING" | "FAIL";
    label: string;
  } | null>(null);
  const [communicationStatus, setCommunicationStatus] = useState<{
    label: string;
    status: string;
  } | null>(null);
  const [operationPeriods, setOperationPeriods] = useState<OperationPeriod[]>([]);

  const activeOperationPeriods = useMemo(
    () => (selectedDate ? getActiveOperationPeriods(selectedDate, operationPeriods) : []),
    [selectedDate, operationPeriods],
  );

  useEffect(() => {
    fetchOperationPeriods()
      .then(setOperationPeriods)
      .catch(() => setOperationPeriods([]));
  }, [location.pathname]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" in window ? ("instant" as ScrollBehavior) : "auto" });
  }, [location.pathname]);

  useEffect(() => {
    if (!selectedDate) {
      setCommunicationStatus(null);
      return;
    }
    loadDashboardSummary(selectedDate, "prev_day")
      .then((summary) =>
        setCommunicationStatus({
          label: summary.meta.communicationStatusLabel,
          status: summary.meta.communicationStatus,
        }),
      )
      .catch(() => setCommunicationStatus(null));
  }, [selectedDate, loadDashboardSummary]);

  useEffect(() => {
    if (!selectedDate) {
      setValidationStatus(null);
      return;
    }
    fetchReportValidation(selectedDate)
      .then((logs) => {
        const severity = getValidationSeverity(logs);
        if (severity === "PASS") {
          setValidationStatus({ severity, label: "데이터 검증 정상" });
          return;
        }
        const issues = summarizeValidationLogs(logs);
        setValidationStatus({
          severity,
          label: severity === "FAIL" ? `데이터 검증 실패 ${issues.length}건` : `데이터 검증 주의 ${issues.length}건`,
        });
      })
      .catch(() => setValidationStatus(null));
  }, [selectedDate]);

  const sidebarClass = sidebarCollapsed ? "imc-sidebar imc-sidebar--collapsed" : "imc-sidebar";

  return (
    <div className="imc-dashboard-shell" style={{ background: palette.bg, color: palette.text }}>
      <aside
        className={sidebarClass}
        style={{
          background: palette.sidebar,
          borderRight: `1px solid ${palette.border}`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <div className="imc-sidebar-label" style={{ fontWeight: 700, fontSize: 13, lineHeight: 1.4 }}>
            중부권광역우편물류센터
          </div>
          <button
            type="button"
            onClick={() => setSidebarCollapsed((value) => !value)}
            aria-label={sidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기"}
            title={sidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기"}
            style={{
              padding: "4px 8px",
              borderRadius: 6,
              border: `1px solid ${palette.border}`,
              background: palette.panelAlt,
              color: palette.muted,
              cursor: "pointer",
              fontSize: 12,
              flexShrink: 0,
            }}
          >
            {sidebarCollapsed ? "»" : "«"}
          </button>
        </div>
        {NAV_ITEMS.map((item) => (
          <div key={item.path}>
            <NavLink
              to={item.path}
              end={item.path === "/"}
              title={item.adminOnly && !isAdmin ? "관리자 전용 메뉴" : item.label}
              style={({ isActive }) => ({
                display: "block",
                padding: "10px 12px",
                borderRadius: 8,
                marginBottom: 6,
                textDecoration: "none",
                background: isActive ? palette.panel : "transparent",
                color: isActive ? palette.text : item.ready ? palette.muted : palette.chartText,
                opacity: item.ready ? 1 : 0.55,
                overflow: "hidden",
              })}
            >
              <span className="imc-nav-text">
                <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{item.label}</span>
                {item.adminOnly ? (
                  <span
                    style={{
                      fontSize: 11,
                      flexShrink: 0,
                      color: isAdmin ? palette.normal : palette.caution,
                    }}
                  >
                    {isAdmin ? "관리자" : "🔒"}
                  </span>
                ) : null}
                {!item.ready ? <span style={{ fontSize: 11, marginLeft: 6 }}>준비중</span> : null}
              </span>
            </NavLink>
            {item.path === "/settings" && isAdmin ? (
              <button
                type="button"
                className="imc-admin-logout"
                onClick={logout}
                style={{
                  width: "100%",
                  marginBottom: 6,
                  padding: "8px 12px",
                  borderRadius: 8,
                  border: `1px solid ${palette.border}`,
                  background: palette.panelAlt,
                  color: palette.muted,
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                관리자 모드 종료
              </button>
            ) : null}
          </div>
        ))}
        <div className="imc-sidebar-filters" style={{ marginTop: 28, paddingTop: 20, borderTop: `1px solid ${palette.border}` }}>
          <div style={{ color: palette.muted, fontSize: 12, marginBottom: 8 }}>조회 일자</div>
          <ReportDateCalendar dates={dates} value={selectedDate} onChange={setSelectedDate} />
          <div style={{ color: palette.muted, fontSize: 12, marginBottom: 8, marginTop: 12 }}>비교 기준</div>
          {COMPARE_OPTIONS.map((option) => (
            <label key={option.value} style={{ display: "block", marginBottom: 6, fontSize: 13 }}>
              <input
                type="radio"
                checked={compare === option.value}
                onChange={() => setCompareBasis(option.value)}
                style={{ marginRight: 8 }}
              />
              {option.label}
            </label>
          ))}
        </div>
      </aside>

      <main className="imc-main">
        <header className="imc-main-header">
          <div className="imc-main-header__title-row">
            <h1 className="imc-main-header__title">중부권IMC 통합관제 대시보드</h1>
            {selectedDate ? (
              <div style={{ color: palette.muted, fontSize: 15 }}>{formatDateWithWeekday(selectedDate)}</div>
            ) : null}
            {communicationStatus ? (
              <CommunicationStatusBadge
                label={communicationStatus.label}
                status={communicationStatus.status}
                size="compact"
              />
            ) : null}
            {validationStatus && validationStatus.severity !== "PASS" ? (
              <ValidationStatusBadge
                label={validationStatus.label}
                status={validationStatus.severity}
                onClick={() => navigate("/reports")}
              />
            ) : null}
            {activeOperationPeriods.map((period) => (
              <OperationPeriodBadge
                key={period.id}
                periodType={period.periodType}
                startDate={period.startDate}
                endDate={period.endDate}
                note={period.note}
              />
            ))}
          </div>
          <ThemeToggle />
        </header>
        {error ? <div style={{ color: palette.critical, marginBottom: 12 }}>{error}</div> : null}
        <Outlet />
      </main>
    </div>
  );
}
