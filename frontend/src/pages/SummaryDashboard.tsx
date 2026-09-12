import { useEffect, useState } from "react";
import { HourlyStaffChart } from "../components/charts/HourlyStaffChart";
import { HourlyVolumeChart } from "../components/charts/HourlyVolumeChart";
import { MachineSortingPieChart } from "../components/charts/MachineSortingPieChart";
import { Panel } from "../components/layout/Panel";
import { PageState } from "../components/PageState";
import { KpiCard } from "../components/kpi/KpiCard";
import {
  AnomalyList,
  EquipmentGaugePanel,
  SafetyCategoryGrid,
  SafetyIncidentPanel,
  TransportPanel,
} from "../components/panels/DashboardPanels";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { useRequestGeneration } from "../hooks/useRequestGeneration";
import type { DashboardSummary } from "../types/dashboard";

const KPI_ORDER = [
  "national_volume",
  "total_volume",
  "dispatch_volume",
  "arrival_volume",
  "remaining_volume",
  "productivity",
  "ips_rate",
  "last_operation_time",
];

function orderKpis(kpis: DashboardSummary["kpis"]) {
  return [...kpis]
    .filter((item) => item.key !== "national_processing_rate")
    .sort((a, b) => {
      const aIndex = KPI_ORDER.indexOf(a.key);
      const bIndex = KPI_ORDER.indexOf(b.key);
      if (aIndex === -1) return 1;
      if (bIndex === -1) return -1;
      return aIndex - bIndex;
    });
}

export default function SummaryDashboard() {
  const { palette } = useTheme();
  const { selectedDate, compare, loadDashboardSummary, getCachedDashboardSummary } = useDashboardFilters();
  const { next, isCurrent, invalidate } = useRequestGeneration();
  const [data, setData] = useState<DashboardSummary | null>(() =>
    selectedDate ? getCachedDashboardSummary(selectedDate, compare) : null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = (date = selectedDate, compareBasis = compare) => {
    if (!date) return;
    const requestId = next();
    const cached = getCachedDashboardSummary(date, compareBasis);
    if (cached && cached.meta.reportDate === date) {
      setData(cached);
      setLoading(false);
      setError(null);
    } else {
      setData(null);
      setLoading(true);
      setError(null);
    }
    loadDashboardSummary(date, compareBasis)
      .then((summary) => {
        if (!isCurrent(requestId)) return;
        setData(summary);
      })
      .catch(() => {
        if (!isCurrent(requestId)) return;
        if (!cached) {
          setError("대시보드 데이터를 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (!isCurrent(requestId)) return;
        setLoading(false);
      });
  };

  useEffect(() => {
    if (!selectedDate) {
      setData(null);
      return;
    }
    loadData(selectedDate, compare);
    return () => invalidate();
  }, [selectedDate, compare]);

  if (!selectedDate) {
    return <PageState empty />;
  }

  if (loading && !data) {
    return <PageState loading />;
  }

  if (error && !data) {
    return <PageState error={error} onRetry={loadData} />;
  }

  if (!data) {
    return <PageState empty />;
  }

  return (
    <div className="imc-summary-compact">
      {data.meta.reportFormat === "compact" ? (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 14px",
            borderRadius: 10,
            border: `1px solid ${palette.caution}`,
            background: palette.panelAlt,
            color: palette.muted,
            fontSize: 13,
          }}
        >
          주말·공휴일 축약형 보고서입니다. 운송·안전·인력 일부 항목은 PDF에 포함되지 않을 수 있습니다.
        </div>
      ) : null}

      <section className="imc-kpi-grid imc-kpi-grid--8">
        {orderKpis(data.kpis).map((item) => (
          <KpiCard key={item.key} item={item} />
        ))}
      </section>

      <section className="imc-summary-row-2-1">
        <Panel title="시간대별 처리물량">
          <HourlyVolumeChart data={data.hourlyVolume} />
        </Panel>
        <Panel title="오늘의 특이사항 / 이상징후">
          <AnomalyList items={data.anomalies} />
        </Panel>
      </section>

      <section className="imc-summary-row-2-1">
        <Panel title="인력 현황">
          <HourlyStaffChart staff={data.hourlyStaff} />
        </Panel>
        <Panel title="운송 현황">
          <TransportPanel transport={data.transport} quotaOverages={data.quotaOverages} />
        </Panel>
      </section>

      <section className="imc-summary-row-3">
        <div className="imc-summary-equipment-stack">
          <Panel title="설비(구분기) 현황">
            <EquipmentGaugePanel equipment={data.equipment} />
          </Panel>
          <Panel title="기계구분율">
            <MachineSortingPieChart data={data.machineSorting} />
          </Panel>
        </div>
        <Panel title="안전 점검 현황">
          <SafetyCategoryGrid safety={data.safety} />
        </Panel>
        <Panel title="재해 현황">
          <SafetyIncidentPanel safety={data.safety} />
        </Panel>
      </section>

      <footer style={{ marginTop: 16, color: palette.muted, fontSize: 12 }}>
        데이터 갱신 기준: {data.meta.reportDate} · PDF 일일소통현황 보고서 기반
      </footer>
    </div>
  );
}
