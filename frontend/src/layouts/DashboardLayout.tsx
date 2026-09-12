import { useEffect, useMemo, useState } from "react";
import { useRequestGeneration } from "../hooks/useRequestGeneration";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ValidationStatusBadge } from "../components/header/ValidationStatusBadge";
import { CommunicationStatusBadge } from "../components/header/CommunicationStatusBadge";
import { OperationPeriodBadge } from "../components/header/OperationPeriodBadge";
import { ThemeToggle } from "../components/header/ThemeToggle";
import { ReportDateCalendar } from "../components/filters/ReportDateCalendar";
import { GUIDE_NAV_ITEM, NAV_ITEMS } from "../config/navigation";
import { useAdminAuth } from "../context/AdminAuthContext";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { fetchDashboardHeader, fetchOperationPeriods } from "../lib/api";
import { COMPARE_OPTIONS } from "../lib/dashboardCompare";
import { formatDateWithWeekday } from "../lib/dateFormat";
import { getActiveOperationPeriods } from "../lib/operationPeriodMatch";
import type { OperationPeriod } from "../types/operationPeriod";

export function DashboardLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { palette } = useTheme();
  const { isAdmin, logout } = useAdminAuth();
  const { dates, selectedDate, setSelectedDate, compare, setCompareBasis, error } = useDashboardFilters();
  const headerRequests = useRequestGeneration();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => window.matchMedia("(max-width: 768px)").matches,
  );
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
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" in window ? ("instant" as ScrollBehavior) : "auto" });
  }, [location.pathname]);

  useEffect(() => {
    if (!selectedDate) {
      setCommunicationStatus(null);
      setValidationStatus(null);
      return;
    }
    const requestId = headerRequests.next();
    setCommunicationStatus(null);
    setValidationStatus(null);
    fetchDashboardHeader(selectedDate)
      .then((header) => {
        if (!headerRequests.isCurrent(requestId)) return;
        setCommunicationStatus({
          label: header.communicationStatusLabel,
          status: header.communicationStatus,
        });
        if (header.validationSeverity === "PASS") {
          setValidationStatus({ severity: "PASS", label: "데이터 검증 정상" });
          return;
        }
        const issueCount = header.validationFailCount + header.validationWarningCount;
        setValidationStatus({
          severity: header.validationSeverity,
          label:
            header.validationSeverity === "FAIL"
              ? `데이터 검증 실패 ${issueCount}건`
              : `데이터 검증 주의 ${issueCount}건`,
        });
      })
      .catch(() => {
        if (!headerRequests.isCurrent(requestId)) return;
        setCommunicationStatus(null);
        setValidationStatus(null);
      });
    return () => headerRequests.invalidate();
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
        <div className="imc-sidebar-body">
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
        </div>
        <div className="imc-sidebar-guide" style={{ borderTop: `1px solid ${palette.border}` }}>
          <NavLink
            to={GUIDE_NAV_ITEM.path}
            title={GUIDE_NAV_ITEM.label}
            style={({ isActive }) => ({
              display: "block",
              padding: "10px 12px",
              borderRadius: 8,
              textDecoration: "none",
              background: isActive ? palette.panel : "transparent",
              color: isActive ? palette.text : palette.muted,
              overflow: "hidden",
            })}
          >
            <span className="imc-nav-text">{GUIDE_NAV_ITEM.label}</span>
          </NavLink>
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
