import { useEffect, useMemo, useState } from "react";
import { BenchmarkTable, type BenchmarkRow } from "../components/analysis/BenchmarkTable";
import { SafetyTrendChart } from "../components/charts/SafetyTrendChart";
import { Modal } from "../components/layout/Modal";
import { AnomalyList, SafetyCategoryGrid, SafetyIncidentPanel } from "../components/panels/DashboardPanels";
import { PageState } from "../components/PageState";
import { buildSafetyTrendChartData } from "../lib/safetyTrendChartData";
import { compareToBenchmarkKey, TREND_OPTIONS } from "../lib/dashboardCompare";
import { useDashboardFilters } from "../context/DashboardFilterContext";
import { useTheme } from "../context/ThemeContext";
import { useRequestGeneration } from "../hooks/useRequestGeneration";
import { fetchSafetyAnalysis } from "../lib/api";
import { severityColor } from "../styles/theme";
import type { SafetyAnalysis, SafetyBenchmark } from "../types/safetyAnalysis";

function formatMetric(value?: number | null, unit = "", decimals = 0) {
  if (value === null || value === undefined) return "-";
  const formatted = unit === "%" ? `${value.toFixed(decimals)}%` : `${value.toFixed(decimals)}${unit}`;
  return formatted;
}

function buildBenchmarkRows(summary: SafetyAnalysis["summary"], benchmark?: SafetyBenchmark): BenchmarkRow[] {
  return [
    {
      label: "재해 건수",
      current: summary.incidentCount,
      benchmark: benchmark?.incidentCount,
      unit: "건",
      higherIsBetter: false,
      decimals: 1,
    },
    {
      label: "주의 이상징후",
      current: summary.warningAnomalyCount,
      benchmark: benchmark?.warningCount,
      unit: "건",
      higherIsBetter: false,
      decimals: 1,
    },
    {
      label: "안전점검 양호율",
      current: summary.safetyPassRate,
      benchmark: benchmark?.safetyPassRate,
      unit: "%",
      higherIsBetter: true,
      decimals: 1,
    },
  ];
}

export default function SafetyAnalysisPage() {
  const { palette } = useTheme();
  const { selectedDate, compare, setCompareBasis, trendView, setVolumeTrendView } = useDashboardFilters();
  const { next, isCurrent, invalidate } = useRequestGeneration();
  const [data, setData] = useState<SafetyAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warningAnomalyModalOpen, setWarningAnomalyModalOpen] = useState(false);
  const [criticalAnomalyModalOpen, setCriticalAnomalyModalOpen] = useState(false);
  const activeBenchmarkKey = compareToBenchmarkKey(compare);

  const loadData = (date = selectedDate) => {
    if (!date) return;
    const requestId = next();
    setData(null);
    setLoading(true);
    setError(null);
    fetchSafetyAnalysis(date)
      .then((payload) => {
        if (!isCurrent(requestId)) return;
        setData(payload);
      })
      .catch(() => {
        if (!isCurrent(requestId)) return;
        setError("안전·이상징후 데이터를 불러오지 못했습니다.");
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
    loadData(selectedDate);
    return () => invalidate();
  }, [selectedDate]);

  const trendData = useMemo(() => {
    if (!data) return null;
    return data.trends?.[trendView] ?? data.dailyTrend;
  }, [data, trendView]);

  const trendTitle = TREND_OPTIONS.find((option) => option.value === trendView)?.label ?? "안전 추세";
  const sharedTrendChartData = useMemo(() => {
    if (!trendData) return null;
    return buildSafetyTrendChartData(trendData, data?.meta.reportDate);
  }, [trendData, data?.meta.reportDate]);

  const warningAnomalies = useMemo(
    () => data?.anomalies.filter((item) => item.severity === "WARNING") ?? [],
    [data],
  );

  const criticalAnomalies = useMemo(
    () => data?.anomalies.filter((item) => item.severity === "CRITICAL") ?? [],
    [data],
  );

  const panelStyle = {
    background: palette.panel,
    border: `1px solid ${palette.border}`,
    borderRadius: 14,
    padding: 16,
  };

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

  const statusColor = severityColor(data.summary.overallStatus, palette);
  const summaryCards = [
    {
      label: "종합 상태",
      value: data.summary.overallLabel ?? "-",
      accent: true,
      color: statusColor,
    },
    { label: "안전점검 양호율", value: formatMetric(data.summary.safetyPassRate, "%", 1) },
    { label: "점검 항목", value: `${data.summary.passedCategoryCount ?? 0}/${data.summary.categoryCount ?? 0}` },
    { label: "재해 건수", value: `${data.summary.incidentCount ?? 0}건`, warning: (data.summary.incidentCount ?? 0) > 0 },
    {
      label: "주의 이상징후",
      value: `${data.summary.warningAnomalyCount ?? 0}건`,
      clickable: warningAnomalies.length >= 1,
      onClick: () => setWarningAnomalyModalOpen(true),
      hint: warningAnomalies.length >= 1 ? "클릭하여 상세 보기" : undefined,
    },
    {
      label: "위험 이상징후",
      value: `${data.summary.criticalAnomalyCount ?? 0}건`,
      clickable: criticalAnomalies.length >= 1,
      onClick: () => setCriticalAnomalyModalOpen(true),
      hint: criticalAnomalies.length >= 1 ? "클릭하여 상세 보기" : undefined,
    },
  ];

  return (
    <>
      <section className="imc-kpi-grid imc-kpi-grid--6">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            role={card.clickable ? "button" : undefined}
            tabIndex={card.clickable ? 0 : undefined}
            onClick={card.clickable ? card.onClick : undefined}
            onKeyDown={
              card.clickable
                ? (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      card.onClick?.();
                    }
                  }
                : undefined
            }
            style={{
              ...panelStyle,
              ...(card.accent
                ? { borderLeft: `4px solid ${card.color ?? palette.caution}` }
                : card.warning
                  ? { borderLeft: `4px solid ${palette.warning}` }
                  : {}),
              ...(card.clickable
                ? {
                    cursor: "pointer",
                    transition: "border-color 0.15s ease, box-shadow 0.15s ease",
                  }
                : {}),
            }}
          >
            <div style={{ color: palette.muted, fontSize: 13, marginBottom: 8 }}>{card.label}</div>
            <div
              style={{
                fontSize: 24,
                fontWeight: 700,
                whiteSpace: "nowrap",
                color: card.color ?? palette.text,
              }}
            >
              {card.value}
            </div>
            {card.hint ? (
              <div style={{ marginTop: 6, fontSize: 11, color: palette.caution }}>{card.hint}</div>
            ) : null}
          </div>
        ))}
      </section>

      <section style={{ display: "grid", gap: 16, marginBottom: 16 }}>
        <div className="imc-analysis-2col">
          <div style={panelStyle}>
            <h3 style={{ margin: "0 0 12px" }}>안전보건 점검 현황</h3>
            <SafetyCategoryGrid safety={data.safety} />
          </div>
          <div style={panelStyle}>
            <h3 style={{ margin: "0 0 12px" }}>운영 이상징후</h3>
            <AnomalyList items={data.anomalies} />
          </div>
        </div>

        <div style={panelStyle}>
          <h3 style={{ margin: "0 0 12px" }}>재해 현황</h3>
          <SafetyIncidentPanel safety={data.safety} displayMode="full" />
        </div>

        <div style={panelStyle}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              marginBottom: 12,
            }}
          >
            <h3 style={{ margin: 0 }}>안전·이상징후 추세</h3>
            <select
              value={trendView}
              onChange={(e) => setVolumeTrendView(e.target.value as typeof trendView)}
              style={{
                padding: "8px 12px",
                background: palette.inputBg,
                color: palette.text,
                border: `1px solid ${palette.border}`,
                borderRadius: 8,
                fontSize: 13,
              }}
            >
              {TREND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          {trendData && sharedTrendChartData ? (
            <SafetyTrendChart
              data={trendData}
              referenceDate={data.meta.reportDate}
              chartData={sharedTrendChartData}
            />
          ) : null}
          <div style={{ marginTop: 8, color: palette.muted, fontSize: 12 }}>
            {trendView === "weekday"
              ? "최근 30업무일 이내 보고서 기준 요일별 평균 안전 지표입니다."
              : `${trendTitle} · 보고서가 수집된 날짜만 표시됩니다.`}
          </div>
        </div>

        <div className="imc-benchmark-grid">
          <BenchmarkTable
            title="전일 대비 기준"
            rows={buildBenchmarkRows(data.summary, data.benchmarks.prevDay)}
            active={activeBenchmarkKey === "prevDay"}
            onSelect={() => setCompareBasis("prev_day")}
          />
          <BenchmarkTable
            title="최근 7업무일 평균"
            rows={buildBenchmarkRows(data.summary, data.benchmarks.avg7d)}
            active={activeBenchmarkKey === "avg7d"}
            onSelect={() => setCompareBasis("7d_avg")}
          />
          <BenchmarkTable
            title="최근 30업무일 평균"
            rows={buildBenchmarkRows(data.summary, data.benchmarks.avg30d)}
            active={activeBenchmarkKey === "avg30d"}
            onSelect={() => setCompareBasis("30d_avg")}
          />
          <BenchmarkTable
            title={`최근 30업무일 이내 동일 요일 평균(${data.benchmarks.sameWeekday?.weekdayLabel ?? "-"})`}
            rows={buildBenchmarkRows(data.summary, data.benchmarks.sameWeekday)}
            active={activeBenchmarkKey === "sameWeekday"}
            onSelect={() => setCompareBasis("same_weekday")}
          />
        </div>
      </section>

      <footer style={{ marginTop: 20, color: palette.muted, fontSize: 12 }}>
        데이터 갱신 기준: {data.meta.reportDate} · PDF 일일소통현황 보고서 기반
      </footer>

      <Modal
        open={warningAnomalyModalOpen}
        title="주의 이상징후"
        description={`${data.meta.reportDate} · ${warningAnomalies.length}건`}
        onClose={() => setWarningAnomalyModalOpen(false)}
      >
        <AnomalyList items={warningAnomalies} />
      </Modal>

      <Modal
        open={criticalAnomalyModalOpen}
        title="위험 이상징후"
        description={`${data.meta.reportDate} · ${criticalAnomalies.length}건`}
        onClose={() => setCriticalAnomalyModalOpen(false)}
      >
        <AnomalyList items={criticalAnomalies} />
      </Modal>
    </>
  );
}
